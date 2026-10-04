"""Minimal-rootfs dependency collection must fail closed, preserving ownership."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from runtime_elf import closure, dependencies
from runtime_inventory import inventory, owners
from runtime_rootfs import assemble, copy


def test_dependency_parser_collects_loader_and_libraries() -> None:
    result = dependencies("libc.so.6 => /lib/libc.so.6 (0x123)\n /lib/ld.so (0x456)\n linux-vdso.so.1 (0x789)")
    assert result == {Path("/lib/libc.so.6"), Path("/lib/ld.so")}
    with pytest.raises(ValueError, match="LIBRARY_MISSING"):
        dependencies("libbroken.so => not found")


def test_closure_follows_dependencies_and_ignores_non_elf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary, library, text = [tmp_path / n for n in ("bin", "lib.so", "data")]
    binary.write_bytes(b"\x7fELFfixture")
    library.write_bytes(b"\x7fELFfixture")
    text.write_text("data")
    def inspect(args: list[str]) -> bytes:
        return (f"lib.so => {library} (0x123)" if args[1] == str(binary) else "").encode()
    monkeypatch.setattr("runtime_elf.run", inspect)
    assert closure([binary, text]) == {library}
    def reject(args: list[str]) -> bytes:
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr("runtime_elf.run", reject)
    with pytest.raises(ValueError, match="ELF_INSPECTION_FAILED"):
        closure([binary])


def test_every_shipped_library_must_have_real_package_owner(tmp_path: Path) -> None:
    library = tmp_path / "lib.so"
    library.write_bytes(b"library")
    database = tmp_path / "dpkg"
    (database / "info").mkdir(parents=True)
    with pytest.raises(ValueError, match="OWNER_MISSING"):
        owners({library}, database)
    (database / "info/libfixture:arm64.list").write_text(str(library) + "\n")
    assert owners({library}, database) == {"libfixture:arm64"}


def test_copy_dereferences_libraries_and_preserves_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"library")
    link = tmp_path / "link"
    link.symlink_to(source)
    root = tmp_path / "root"
    copy(link, root)
    shipped = root / link.relative_to("/")
    assert shipped.read_bytes() == b"library" and not shipped.is_symlink()
    with pytest.raises(ValueError, match="DESTINATION_EXISTS"):
        assemble(root)


def test_missing_metadata_cannot_hide_a_shipped_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "dpkg"
    database.mkdir()
    (database / "status").write_text("Package: base-files\nArchitecture: all\n\n")
    monkeypatch.setattr("runtime_inventory.owners", lambda files, database: {"libfixture:arm64"})
    with pytest.raises(ValueError, match="PACKAGE_METADATA_MISSING"):
        inventory(tmp_path / "root", set(), database)
