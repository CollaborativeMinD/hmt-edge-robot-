"""Pinned host patches cannot escape the disposable image or change identity."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from appliance_host import install, packages


def config() -> dict:
    return {"packages": [{"name": "libfixture", "version": "1.2-3", "url": "https://deb.debian.org/library.deb", "sha256": hashlib.sha256(b"deb").hexdigest()}]}


@pytest.mark.parametrize("change", [{"name": "../etc"}, {"version": "1;id"}, {"extra": True}])
def test_update_catalog_rejects_untrusted_fields(change: dict) -> None:
    value = config()
    value["packages"][0].update(change)
    with pytest.raises(ValueError, match="HOST_UPDATE"):
        packages(value)


def test_update_catalog_rejects_duplicate_or_missing_packages() -> None:
    value = config()
    value["packages"] *= 2
    with pytest.raises(ValueError, match="DUPLICATE"):
        packages(value)
    with pytest.raises(ValueError, match="CATALOG"):
        packages({})


def test_install_rejects_live_root_before_running_any_command() -> None:
    with pytest.raises(ValueError, match="DISPOSABLE_ARM64"):
        install(Path("/"), config())


def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("appliance_host.ROOT", tmp_path)
    monkeypatch.setattr("appliance_host.platform.machine", lambda: "aarch64")
    monkeypatch.setattr(Path, "is_mount", lambda self: True)
    root = tmp_path / "build/mount-root"
    (root / "usr/sbin").mkdir(parents=True)
    source = tmp_path / "build/inputs/updates/libfixture.deb"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"deb")
    return root


def test_install_rejects_changed_bytes_and_wrong_architecture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = fixture(tmp_path, monkeypatch)
    value = config()
    value["packages"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="CHECKSUM"):
        install(root, value)
    (root / "usr/share/hmt/updates").rmdir()
    monkeypatch.setattr("appliance_host.run", lambda args: b"Package: libfixture\nVersion: 1.2-3\nArchitecture: amd64\n")
    with pytest.raises(ValueError, match="PACKAGE_MISMATCH"):
        install(root, config())


def test_install_checks_package_audit_and_restores_service_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = fixture(tmp_path, monkeypatch)
    def execute(args: list[str], timeout: int = 30) -> bytes:
        if args[0] == "/usr/bin/dpkg-deb":
            return b"Package: libfixture\nVersion: 1.2-3\nArchitecture: arm64\n"
        if args[-1] == "--audit":
            return b"package remains unconfigured"
        return b"installed"
    monkeypatch.setattr("appliance_host.run", execute)
    with pytest.raises(ValueError, match="AUDIT_FAILED"):
        install(root, config())
    assert not (root / "usr/sbin/policy-rc.d").exists()
    assert not (root / "usr/share/hmt/host-updates.json").exists()


@pytest.mark.parametrize("correct", [True, False])
def test_exact_readback_is_required_and_temporary_archives_are_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, correct: bool) -> None:
    root = fixture(tmp_path, monkeypatch)
    def execute(args: list[str], timeout: int = 30) -> bytes:
        if args[0] == "/usr/bin/dpkg-deb":
            return b"Package: libfixture\nVersion: 1.2-3\nArchitecture: arm64\n"
        if "--show" in args:
            return b"libfixture\t1.2-3\tarm64\n" if correct else b"libfixture\t9.9\tarm64\n"
        return b""
    monkeypatch.setattr("appliance_host.run", execute)
    if not correct:
        with pytest.raises(ValueError, match="READBACK_MISMATCH"):
            install(root, config())
    else:
        assert install(root, config())["security_admission"] == "HOLD"
        assert not (root / "usr/share/hmt/updates").exists()
        assert (root / "usr/share/hmt/host-updates.json").is_file()
    assert not (root / "usr/sbin/policy-rc.d").exists()
