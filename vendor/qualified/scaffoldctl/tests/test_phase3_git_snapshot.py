from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from phase3_support import git, init_repository
from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import (
    GitObjectSnapshot,
    GitRepository,
    _make_matrix,
    _parse_matrix_records,
)
from scaffoldctl.integrity import hash_payload
from scaffoldctl.perimeter import discover_boundaries, validate_index_snapshot, validate_snapshot
from scaffoldctl.phase3_models import (
    GitObjectEntry,
    GitObjectFormat,
    GitObjectMatrix,
    GitSnapshotSource,
    PerimeterOperation,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus


def _baseline(repository: GitRepository) -> GitObjectSnapshot:
    return GitObjectSnapshot(repository, repository.capture_tree_matrix("HEAD"))


def test_index_snapshot_reads_staged_blobs_not_unstaged_worktree(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)
    baseline = _baseline(repository)
    staged = GitObjectSnapshot(repository, repository.capture_index_matrix())
    staged_readme = staged.read_bytes("README.md")
    root.joinpath("README.md").write_text("\n".join(f"line {item}" for item in range(120)))
    assert staged.read_bytes("README.md") == staged_readme
    assert (
        validate_index_snapshot(repository, baseline=baseline).validationStatus
        is ValidationStatus.PASS
    )
    git(root, "add", "README.md")
    rejected = validate_index_snapshot(repository, baseline=baseline)
    assert rejected.exitCode == 1
    assert ReasonCode.LINE_COUNT_INVALID in rejected.boundaries[0].reasonCodes


def test_missing_trifecta_is_explicit_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    root.joinpath("Start_here.md").unlink()
    git(root, "add", "--all")
    receipt = validate_index_snapshot(GitRepository(root))
    assert receipt.exitCode == 1
    assert ReasonCode.DOCUMENT_MISSING in receipt.boundaries[0].reasonCodes


def test_baseline_union_detects_deleted_nested_boundary(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root, nested=True)
    for path in root.joinpath("docs/system").iterdir():
        path.unlink()
    root.joinpath("docs/system").rmdir()
    git(root, "add", "--all")
    repository = GitRepository(root)
    receipt = validate_index_snapshot(repository, baseline=_baseline(repository))
    records = {record.targetPath: record for record in receipt.boundaries}
    assert tuple(records) == (".", "docs/system")
    assert records["docs/system"].admitted is False
    assert ReasonCode.TARGET_MISSING in records["docs/system"].reasonCodes


def test_tree_and_index_matrices_have_object_parity(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root, nested=True)
    repository = GitRepository(root)
    index = repository.capture_index_matrix()
    tree = repository.capture_tree_matrix("HEAD")
    assert index.contentMatrixSha256 == tree.contentMatrixSha256
    assert tuple(item.relativePath for item in index.entries) == tuple(
        item.relativePath for item in tree.entries
    )
    tree_receipt = validate_snapshot(
        GitObjectSnapshot(repository, tree), PerimeterOperation.VALIDATE_TREE
    )
    assert tree_receipt.exitCode == 0
    assert tree_receipt.sourceRef == tree.sourceRef


def test_unborn_head_is_not_confused_with_discovery_failure(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root, commit=False)
    repository = GitRepository(root)
    assert repository.capture_optional_head_matrix() is None
    receipt = validate_index_snapshot(repository)
    assert receipt.exitCode == 0


def test_non_repository_and_nested_root_are_rejected(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository(plain)
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED
    root = tmp_path / "repo"
    init_repository(root, nested=True)
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository(root / "docs")
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED


def test_revision_resolution_rejects_malformed_and_missing_values(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)
    for value in ("", "missing", "HEAD\nmain", "x" * 257):
        with pytest.raises(PhaseThreeError) as raised:
            repository.capture_tree_matrix(value)
        assert raised.value.reason_code is ReasonCode.GIT_REVISION_INVALID


def test_index_parser_rejects_unmerged_and_malformed_records() -> None:
    oid = b"a" * 40
    with pytest.raises(PhaseThreeError) as raised:
        _parse_matrix_records(b"100644 blob " + oid + b" 1 2\tREADME.md\0", include_stage=True)
    assert raised.value.reason_code is ReasonCode.GIT_INDEX_UNMERGED
    with pytest.raises(PhaseThreeError) as raised:
        _parse_matrix_records(b"broken\0", include_stage=True)
    assert raised.value.reason_code is ReasonCode.GIT_MATRIX_INVALID
    with pytest.raises(PhaseThreeError) as raised:
        _parse_matrix_records(
            b"100644 blob " + oid + b" invalid 0\tREADME.md\0", include_stage=True
        )
    assert raised.value.reason_code is ReasonCode.GIT_MATRIX_INVALID


def test_matrix_schema_rejects_collisions_drift_and_invalid_source() -> None:
    entries = tuple(
        GitObjectEntry(
            relativePath=path,
            objectMode="100644",
            objectType="blob",
            objectId="a" * 40,
            objectSize=1,
            stage=0,
        )
        for path in ("README.md", "readme.md")
    )
    with pytest.raises(PhaseThreeError) as raised:
        _make_matrix(GitSnapshotSource.INDEX, "INDEX", GitObjectFormat.SHA1, entries)
    assert raised.value.reason_code is ReasonCode.GIT_MATRIX_INVALID
    good = _make_matrix(GitSnapshotSource.INDEX, "INDEX", GitObjectFormat.SHA1, entries[:1])
    with pytest.raises(ValidationError):
        GitObjectMatrix.model_validate({**good.model_dump(mode="python"), "matrixSha256": "0" * 64})
    with pytest.raises(ValidationError):
        GitObjectMatrix.model_validate(
            {
                **good.model_dump(mode="python"),
                "sourceKind": GitSnapshotSource.TREE,
                "sourceRef": "z" * 40,
                "matrixSha256": hash_payload(
                    {
                        "contentMatrixSha256": good.contentMatrixSha256,
                        "objectFormat": GitObjectFormat.SHA1,
                        "sourceKind": GitSnapshotSource.TREE,
                        "sourceRef": "z" * 40,
                    }
                ),
            }
        )


def test_snapshot_types_listing_and_bounds(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root, nested=True)
    repository = GitRepository(root)
    snapshot = GitObjectSnapshot(repository, repository.capture_index_matrix())
    assert snapshot.kind(".").value == "directory"
    assert snapshot.kind("docs").value == "directory"
    assert snapshot.kind("absent").value == "missing"
    assert snapshot.list_dir(".") == tuple(sorted(snapshot.list_dir("."), key=str.encode))
    assert snapshot.entry("README.md").sha256 is not None
    with pytest.raises(PhaseThreeError):
        snapshot.read_bytes("README.md", maximum_bytes=1)
    with pytest.raises(PhaseThreeError):
        snapshot.read_bytes("absent")
    with pytest.raises(PhaseThreeError):
        snapshot.list_dir("README.md")
    with pytest.raises(PhaseThreeError):
        snapshot.kind("../escape")


def test_index_recapture_change_forces_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)
    original = repository.capture_index_matrix()
    changed_entry = GitObjectEntry(
        relativePath="unobserved.txt",
        objectMode="100644",
        objectType="blob",
        objectId="b" * 40,
        objectSize=0,
        stage=0,
    )
    changed = _make_matrix(
        GitSnapshotSource.INDEX,
        "INDEX",
        original.objectFormat,
        tuple(sorted((*original.entries, changed_entry), key=lambda item: item.relativePath)),
    )
    calls = iter((original, changed))
    monkeypatch.setattr(repository, "capture_index_matrix", lambda: next(calls))
    receipt = validate_index_snapshot(repository)
    assert receipt.exitCode == 1
    assert ReasonCode.GIT_INDEX_CHANGED in receipt.reasonCodes


def test_boundary_discovery_is_sorted_and_deduplicated(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root, nested=True)
    repository = GitRepository(root)
    snapshot = GitObjectSnapshot(repository, repository.capture_index_matrix())
    assert discover_boundaries(snapshot, snapshot) == (".", "docs/system")


def test_git_command_transport_errors_are_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def transport_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise OSError("transport unavailable")

    monkeypatch.setattr(subprocess, "run", transport_error)
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository._bootstrap(tmp_path, ("rev-parse", "--show-toplevel"))
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED
    repository = object.__new__(GitRepository)
    repository.root = tmp_path
    repository.git_dir = tmp_path
    with pytest.raises(PhaseThreeError) as raised:
        repository._run_status(("status",))
    assert raised.value.reason_code is ReasonCode.GIT_COMMAND_FAILED


def test_repository_constructor_rejects_invalid_command_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    init_repository(root)

    def invalid_root(_cls: type[GitRepository], _root: Path, _arguments: tuple[str, ...]) -> bytes:
        return b"\xff"

    monkeypatch.setattr(GitRepository, "_bootstrap", classmethod(invalid_root))
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository(root)
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED

    def invalid_git_dir(
        _cls: type[GitRepository], _root: Path, arguments: tuple[str, ...]
    ) -> bytes:
        return str(root).encode() if arguments[-1] == "--show-toplevel" else b"relative"

    monkeypatch.setattr(GitRepository, "_bootstrap", classmethod(invalid_git_dir))
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository(root)
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED

    def valid_discovery(
        _cls: type[GitRepository], _root: Path, arguments: tuple[str, ...]
    ) -> bytes:
        return str(root if arguments[-1] == "--show-toplevel" else root / ".git").encode()

    monkeypatch.setattr(GitRepository, "_bootstrap", classmethod(valid_discovery))
    monkeypatch.setattr(GitRepository, "_run", lambda *_args, **_kwargs: b"unsupported")
    with pytest.raises(PhaseThreeError) as raised:
        GitRepository(root)
    assert raised.value.reason_code is ReasonCode.GIT_DISCOVERY_FAILED


def test_blob_protocol_rejects_every_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)
    blob = repository.capture_index_matrix().entries[0]
    commit = GitObjectEntry(
        relativePath="module",
        objectMode="160000",
        objectType="commit",
        objectId="a" * 40,
        objectSize=None,
        stage=0,
    )
    with pytest.raises(PhaseThreeError) as raised:
        repository.read_blob(commit)
    assert raised.value.reason_code is ReasonCode.GIT_OBJECT_TYPE_INVALID
    for response, reason in (
        (b"incomplete", ReasonCode.GIT_OBJECT_MISSING),
        (f"{blob.objectId} tree 1\nx\n".encode(), ReasonCode.GIT_OBJECT_TYPE_INVALID),
        (f"{blob.objectId} blob invalid\n".encode(), ReasonCode.GIT_OBJECT_MISSING),
        (f"{'b' * 40} blob 1\nx\n".encode(), ReasonCode.GIT_OBJECT_MISSING),
    ):
        repository._blob_cache.clear()
        monkeypatch.setattr(repository, "_run", lambda *_args, value=response, **_kwargs: value)
        with pytest.raises(PhaseThreeError) as raised:
            repository.read_blob(blob)
        assert raised.value.reason_code is reason


def test_optional_head_discovery_rejects_ambiguous_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)

    def result(code: int, output: bytes = b"") -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(("git",), code, output, b"")

    sequences = (
        (
            (result(0, b"\xff"),),
            ReasonCode.GIT_REVISION_INVALID,
        ),
        (
            (result(1), result(1)),
            ReasonCode.GIT_REVISION_INVALID,
        ),
        (
            (result(1), result(0, b"\xff")),
            ReasonCode.GIT_REVISION_INVALID,
        ),
        (
            (result(1), result(0, b"refs/tags/not-a-branch\n")),
            ReasonCode.GIT_REVISION_INVALID,
        ),
        (
            (result(1), result(0, b"refs/heads/main\n"), result(2)),
            ReasonCode.GIT_REVISION_INVALID,
        ),
    )
    for values, reason in sequences:
        calls = iter(values)
        monkeypatch.setattr(
            repository,
            "_run_status",
            lambda *_args, sequence=calls, **_kwargs: next(sequence),
        )
        with pytest.raises(PhaseThreeError) as raised:
            repository.capture_optional_head_matrix()
        assert raised.value.reason_code is reason


def test_parser_reports_mode_and_path_failures_separately() -> None:
    oid = b"a" * 40
    with pytest.raises(PhaseThreeError) as raised:
        _parse_matrix_records(b"100600 blob " + oid + b" 1 0\tREADME.md\0", include_stage=True)
    assert raised.value.reason_code is ReasonCode.GIT_OBJECT_MODE_INVALID
    with pytest.raises(PhaseThreeError) as raised:
        _parse_matrix_records(b"100644 blob " + oid + b" 1 0\t../escape\0", include_stage=True)
    assert raised.value.reason_code is ReasonCode.GIT_PATH_INVALID


def test_snapshot_factories_and_nonfile_modes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    assert GitObjectSnapshot.from_index(root).matrix.sourceKind is GitSnapshotSource.INDEX
    assert GitObjectSnapshot.from_tree(root, "HEAD").matrix.sourceKind is GitSnapshotSource.TREE
    repository = GitRepository(root)
    entries = (
        GitObjectEntry(
            relativePath="link",
            objectMode="120000",
            objectType="blob",
            objectId="a" * 40,
            objectSize=3,
            stage=0,
        ),
        GitObjectEntry(
            relativePath="module",
            objectMode="160000",
            objectType="commit",
            objectId="b" * 40,
            objectSize=None,
            stage=0,
        ),
    )
    snapshot = GitObjectSnapshot(
        repository,
        _make_matrix(GitSnapshotSource.INDEX, "INDEX", GitObjectFormat.SHA1, entries),
    )
    assert snapshot.kind("link").value == "symlink"
    assert snapshot.kind("module").value == "other"
    assert snapshot.list_entries("missing") == ()


def test_run_and_resolved_object_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    repository = GitRepository(root)
    monkeypatch.setattr(
        repository,
        "_run_status",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(("git",), 1, b"", b""),
    )
    with pytest.raises(PhaseThreeError) as raised:
        repository._run(("status",))
    assert raised.value.reason_code is ReasonCode.GIT_COMMAND_FAILED
    monkeypatch.setattr(repository, "_run", lambda *_args, **_kwargs: b"z" * 40)
    with pytest.raises(PhaseThreeError) as raised:
        repository.resolve_tree("HEAD")
    assert raised.value.reason_code is ReasonCode.GIT_REVISION_INVALID
