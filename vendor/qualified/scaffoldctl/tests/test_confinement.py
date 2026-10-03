import os
import stat
from pathlib import Path

import pytest

import scaffoldctl.confinement as confinement
from scaffoldctl.confinement import ConfinedRoot
from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.reason_codes import ReasonCode


def test_platform_and_confined_path_contract(tmp_path: Path) -> None:
    assert confinement.platform_capabilities_available()
    root = ConfinedRoot(tmp_path)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_directory("/absolute")
    assert captured.value.reason_code is ReasonCode.PATH_ABSOLUTE
    with pytest.raises(PhaseTwoError) as captured:
        root.open_parent("../escape")
    assert captured.value.reason_code is ReasonCode.PATH_TRAVERSAL


def test_open_root_maps_open_fstat_and_identity_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ConfinedRoot(tmp_path)
    original_open = os.open

    def fail_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == tmp_path:
            raise OSError("injected")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", fail_open)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_root()
    assert captured.value.reason_code is ReasonCode.ROOT_INVALID
    monkeypatch.setattr(os, "open", original_open)
    monkeypatch.setattr(os, "fstat", lambda descriptor: (_ for _ in ()).throw(OSError()))
    with pytest.raises(PhaseTwoError) as captured:
        root.open_root()
    assert captured.value.reason_code is ReasonCode.ROOT_INVALID
    monkeypatch.undo()
    root._identity = (0, 0)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_root()
    assert captured.value.reason_code is ReasonCode.ROOT_INVALID


def test_open_directory_creates_without_receipt_and_rejects_symlink(
    tmp_path: Path,
) -> None:
    root = ConfinedRoot(tmp_path)
    descriptor = root.open_directory("new/nested", create=True)
    assert descriptor is not None
    os.close(descriptor)
    assert (tmp_path / "new" / "nested").is_dir()
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_directory("link/child")
    assert captured.value.reason_code is ReasonCode.PATH_SYMLINK_REJECTED


def test_open_directory_maps_component_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "nested").mkdir()
    root = ConfinedRoot(tmp_path)
    original = os.stat

    def fail_stat(
        path: object,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        if path == "nested" and dir_fd is not None:
            raise OSError("injected")
        return original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", fail_stat)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_directory("nested")
    assert captured.value.reason_code is ReasonCode.PATH_SYMLINK_REJECTED


def test_stat_and_file_missing_paths_are_reason_coded(tmp_path: Path) -> None:
    root = ConfinedRoot(tmp_path)
    assert root.stat(".") is not None
    assert root.stat("missing/child") is None
    with pytest.raises(PhaseTwoError) as captured:
        root.open_file("missing/child")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE
    with pytest.raises(PhaseTwoError) as captured:
        root.open_file("missing")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE


def test_stat_maps_race_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "file").write_text("data", encoding="utf-8")
    root = ConfinedRoot(tmp_path)
    original = os.stat

    def fail_stat(
        path: object,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        if path == "file" and dir_fd is not None:
            raise OSError("injected")
        return original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", fail_stat)
    with pytest.raises(PhaseTwoError) as captured:
        root.stat("file")
    assert captured.value.reason_code is ReasonCode.PATH_TYPE_INVALID


def test_open_file_rechecks_descriptor_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "file").write_text("data", encoding="utf-8")
    root = ConfinedRoot(tmp_path)
    original = os.fstat
    calls = 0

    def changed_type(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            observed = original(descriptor)
            values = list(observed)
            values[0] = stat.S_IFDIR | 0o755
            return os.stat_result(values)
        return original(descriptor)

    monkeypatch.setattr(os, "fstat", changed_type)
    with pytest.raises(PhaseTwoError) as captured:
        root.open_file("file")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE


def test_read_file_maps_descriptor_size_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "file").write_text("data", encoding="utf-8")
    root = ConfinedRoot(tmp_path)
    original = os.fstat
    calls = 0

    def fail_third(descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected")
        return original(descriptor)

    monkeypatch.setattr(os, "fstat", fail_third)
    with pytest.raises(PhaseTwoError) as captured:
        root.read_file("file")
    assert captured.value.reason_code is ReasonCode.DOCUMENT_NOT_FILE


def test_list_and_remove_missing_directory_paths(tmp_path: Path) -> None:
    root = ConfinedRoot(tmp_path)
    assert root.list_entries("missing") == ()
    with pytest.raises(FileNotFoundError):
        root.remove_directory("missing/child")


def test_list_entries_maps_scan_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ConfinedRoot(tmp_path)
    monkeypatch.setattr(os, "scandir", lambda descriptor: (_ for _ in ()).throw(OSError()))
    with pytest.raises(PhaseTwoError) as captured:
        root.list_entries(".")
    assert captured.value.reason_code is ReasonCode.PATH_TYPE_INVALID
