import os
from pathlib import Path

import pytest

import scaffoldctl.confinement as confinement
from scaffoldctl.confinement import ConfinedRoot
from scaffoldctl.exceptions import PhaseTwoError, TransactionError
from scaffoldctl.phase2_models import EntryKind
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.snapshot import (
    OverlaySnapshot,
    WorktreeSnapshot,
    canonical_repository_root,
    collision_key,
    snapshot_digest,
)
from scaffoldctl.transaction import AtomicBatchWriter, CommitRecord


def test_repository_root_requires_real_non_symlink_directory(tmp_path: Path) -> None:
    assert canonical_repository_root(tmp_path) == tmp_path
    missing = tmp_path / "missing"
    with pytest.raises(PhaseTwoError) as captured:
        canonical_repository_root(missing)
    assert captured.value.reason_code is ReasonCode.ROOT_INVALID
    regular = tmp_path / "file"
    regular.write_text("x", encoding="utf-8")
    with pytest.raises(PhaseTwoError):
        canonical_repository_root(regular)
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PhaseTwoError):
        canonical_repository_root(link)


def test_confined_root_rejects_unsupported_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(confinement, "platform_capabilities_available", lambda: False)
    with pytest.raises(PhaseTwoError) as captured:
        ConfinedRoot(tmp_path)
    assert captured.value.reason_code is ReasonCode.PLATFORM_UNSUPPORTED


def test_snapshot_classifies_reads_lists_and_hashes(tmp_path: Path) -> None:
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "file.txt").write_bytes(b"hello")
    (tmp_path / "link").symlink_to(tmp_path / "dir" / "file.txt")
    snapshot = WorktreeSnapshot(tmp_path)
    assert snapshot.kind("missing") is EntryKind.MISSING
    assert snapshot.kind("dir") is EntryKind.DIRECTORY
    assert snapshot.kind("dir/file.txt") is EntryKind.FILE
    assert snapshot.kind("link") is EntryKind.SYMLINK
    assert snapshot.list_dir("dir") == ("file.txt",)
    assert snapshot.read_bytes("dir/file.txt") == b"hello"
    entry = snapshot.entry("dir/file.txt")
    assert entry.sizeBytes == 5 and entry.sha256 is not None
    assert snapshot.entry("dir/file.txt", include_hash=False).sha256 is None
    assert snapshot.entry("missing").kind is EntryKind.MISSING


def test_snapshot_classifies_special_file_as_other(tmp_path: Path) -> None:
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert WorktreeSnapshot(tmp_path).kind("fifo") is EntryKind.OTHER


def test_snapshot_enforces_size_type_and_symlink_boundaries(tmp_path: Path) -> None:
    (tmp_path / "file").write_bytes(b"12345")
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "link").symlink_to(tmp_path / "file")
    snapshot = WorktreeSnapshot(tmp_path)
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.read_bytes("file", maximum_bytes=4)
    assert captured.value.reason_code is ReasonCode.DOCUMENT_SIZE_INVALID
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.read_bytes("dir")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.read_bytes("dir/link")
    assert captured.value.reason_code is ReasonCode.PATH_SYMLINK_REJECTED
    with pytest.raises(PhaseTwoError):
        snapshot.list_dir("file")


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/absolute", ReasonCode.PATH_ABSOLUTE),
        ("../escape", ReasonCode.PATH_TRAVERSAL),
        ("a/../b", ReasonCode.PATH_TRAVERSAL),
        ("a b", ReasonCode.PATH_TRAVERSAL),
    ],
)
def test_snapshot_rejects_invalid_member_paths(
    tmp_path: Path,
    path: str,
    reason: ReasonCode,
) -> None:
    with pytest.raises(PhaseTwoError) as captured:
        WorktreeSnapshot(tmp_path).kind(path)
    assert captured.value.reason_code is reason


def test_snapshot_rejects_non_directory_parent(tmp_path: Path) -> None:
    (tmp_path / "parent").write_text("not-dir", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        WorktreeSnapshot(tmp_path).kind("parent/child")
    assert captured.value.reason_code is ReasonCode.PATH_TYPE_INVALID


def test_case_and_nfkc_collisions_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("a", encoding="utf-8")
    (tmp_path / "readme.md").write_text("b", encoding="utf-8")
    snapshot = WorktreeSnapshot(tmp_path)
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.list_dir(".")
    assert captured.value.reason_code is ReasonCode.PATH_CASE_COLLISION
    assert collision_key("\uff2bey") == collision_key("Key")


def test_wrong_case_lookup_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "readme.md").write_text("a", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        WorktreeSnapshot(tmp_path).kind("README.md")
    assert captured.value.reason_code is ReasonCode.PATH_CASE_COLLISION


def test_overlay_supplies_virtual_files_and_directories(tmp_path: Path) -> None:
    base = WorktreeSnapshot(tmp_path)
    overlay = OverlaySnapshot(
        base,
        {
            "nested/README.md": b"hello",
            "nested/Index.md": b"index",
        },
    )
    assert overlay.kind("nested") is EntryKind.DIRECTORY
    assert overlay.kind("nested/README.md") is EntryKind.FILE
    assert overlay.kind("missing") is EntryKind.MISSING
    assert overlay.list_dir("nested") == ("Index.md", "README.md")
    assert overlay.read_bytes("nested/README.md") == b"hello"
    assert overlay.entry("nested/README.md").sha256 is not None
    assert overlay.entry("nested/README.md", include_hash=False).sha256 is None
    with pytest.raises(PhaseTwoError) as captured:
        overlay.read_bytes("nested/README.md", maximum_bytes=1)
    assert captured.value.reason_code is ReasonCode.DOCUMENT_SIZE_INVALID


def test_overlay_merges_base_and_rejects_invalid_paths(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "base.txt").write_text("base", encoding="utf-8")
    base = WorktreeSnapshot(tmp_path)
    overlay = OverlaySnapshot(base, {"nested/new.txt": b"new"})
    assert overlay.list_dir("nested") == ("base.txt", "new.txt")
    assert overlay.read_bytes("nested/base.txt") == b"base"
    with pytest.raises(PhaseTwoError):
        OverlaySnapshot(base, {"../escape": b"bad"})


def test_overlay_detects_case_collision_with_base(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("base", encoding="utf-8")
    overlay = OverlaySnapshot(WorktreeSnapshot(tmp_path), {"readme.md": b"overlay"})
    with pytest.raises(PhaseTwoError) as captured:
        overlay.list_dir(".")
    assert captured.value.reason_code is ReasonCode.PATH_CASE_COLLISION


def test_snapshot_digest_is_stable_sensitive_and_supports_ignored_names(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("one", encoding="utf-8")
    snapshot = WorktreeSnapshot(tmp_path)
    paths = ("README.md", "missing")
    first = snapshot_digest(snapshot, ".", paths)
    assert first == snapshot_digest(snapshot, ".", paths)
    (tmp_path / "unrelated").write_text("x", encoding="utf-8")
    second = snapshot_digest(WorktreeSnapshot(tmp_path), ".", paths)
    assert first != second
    ignored = snapshot_digest(
        WorktreeSnapshot(tmp_path),
        ".",
        paths,
        ignored_names=("unrelated",),
    )
    assert ignored == first
    (tmp_path / "unrelated").unlink()
    (tmp_path / "unrelated").mkdir()
    kind_changed = snapshot_digest(WorktreeSnapshot(tmp_path), ".", paths)
    assert kind_changed != second


def test_atomic_batch_publish_and_finalize(tmp_path: Path) -> None:
    writer = AtomicBatchWriter(tmp_path)
    record = writer.commit({"nested/a.txt": b"a", "nested/b.txt": b"b"})
    assert record.created_paths == ("nested/a.txt", "nested/b.txt")
    assert (tmp_path / "nested" / "a.txt").read_bytes() == b"a"
    assert all(temporary.exists() for temporary, _ in record.staged_pairs)
    record.finalize()
    assert record.finalized
    assert all(not temporary.exists() for temporary, _ in record.staged_pairs)
    record.finalize()


def test_finalize_failure_remains_safely_rollbackable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = AtomicBatchWriter(tmp_path).commit({"a.txt": b"a", "b.txt": b"b"})
    original = os.unlink
    calls = 0

    def injected(name: object, *, dir_fd: int | None = None) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        original(name, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", injected)
    with pytest.raises(OSError):
        record.finalize()
    monkeypatch.setattr(os, "unlink", original)
    assert record.rollback()
    assert not (tmp_path / "a.txt").exists()
    assert not (tmp_path / "b.txt").exists()


def test_commit_record_rolls_back_only_its_hardlinks(tmp_path: Path) -> None:
    record = AtomicBatchWriter(tmp_path).commit({"new/a.txt": b"a"})
    assert record.rollback()
    assert not (tmp_path / "new" / "a.txt").exists()
    assert not (tmp_path / "new").exists()


def test_writer_refuses_existing_content_without_overwrite(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("user", encoding="utf-8")
    with pytest.raises(TransactionError) as captured:
        AtomicBatchWriter(tmp_path).commit({"a.txt": b"engine"})
    assert captured.value.rollback_complete
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "user"


def test_writer_rejects_non_directory_parent(tmp_path: Path) -> None:
    (tmp_path / "parent").write_text("file", encoding="utf-8")
    with pytest.raises(TransactionError) as captured:
        AtomicBatchWriter(tmp_path).commit({"parent/a.txt": b"a"})
    assert captured.value.rollback_complete


def test_stage_failure_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fsync(descriptor: int) -> None:
        raise OSError("injected")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    descriptor = ConfinedRoot(tmp_path).open_root()
    try:
        with pytest.raises(OSError):
            AtomicBatchWriter._stage(descriptor, b"data")
    finally:
        os.close(descriptor)
    assert not tuple(tmp_path.glob(".scaffoldctl-*.tmp"))


def test_writer_rolls_back_mid_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = AtomicBatchWriter(tmp_path)
    original = writer._publish
    calls = 0

    def injected(link: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        original(link)  # type: ignore[arg-type]

    monkeypatch.setattr(writer, "_publish", injected)
    with pytest.raises(TransactionError) as captured:
        writer.commit({"nested/a.txt": b"a", "nested/b.txt": b"b"})
    assert captured.value.rollback_complete
    assert not (tmp_path / "nested").exists()
    assert not tuple(tmp_path.rglob(".scaffoldctl-*.tmp"))


def test_rollback_detects_replaced_destination(tmp_path: Path) -> None:
    record = AtomicBatchWriter(tmp_path).commit({"a.txt": b"engine"})
    final = tmp_path / "a.txt"
    replacement = tmp_path / "replacement"
    replacement.write_text("user", encoding="utf-8")
    os.replace(replacement, final)
    assert not record.rollback()
    assert final.read_text(encoding="utf-8") == "user"


def test_rollback_reports_nonempty_created_directory(tmp_path: Path) -> None:
    created = tmp_path / "created"
    created.mkdir()
    (created / "user.txt").write_text("user", encoding="utf-8")
    record = CommitRecord(tmp_path, ConfinedRoot(tmp_path), (), ("created",))
    assert not record.rollback()
    assert created.exists()


def test_snapshot_maps_directory_scan_and_open_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = WorktreeSnapshot(tmp_path)

    def fail_scandir(path: object) -> object:
        raise OSError("injected")

    monkeypatch.setattr(os, "scandir", fail_scandir)
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.kind("file")
    assert captured.value.reason_code is ReasonCode.PATH_TYPE_INVALID


def test_snapshot_maps_open_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "file"
    path.write_text("data", encoding="utf-8")
    snapshot = WorktreeSnapshot(tmp_path)

    original = os.open

    def fail_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == "file":
            raise OSError("injected")
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", fail_open)
    with pytest.raises(PhaseTwoError) as captured:
        snapshot.read_bytes("file")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE
