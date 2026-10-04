"""Assemble a shell-free Python runtime with audited native-library closure."""
from __future__ import annotations

import shutil
from pathlib import Path

from runtime_elf import closure
from runtime_inventory import inventory

OMITTED = ("_uuid", "_curses", "readline", "_tkinter")


def copy(file: Path, root: Path) -> None:
    target = root / file.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, target, follow_symlinks=True)


def assemble(root: Path) -> None:
    if root.exists():
        raise ValueError("RUNTIME_DESTINATION_EXISTS")
    python = root / "usr/local"
    python.mkdir(parents=True)
    shutil.copytree("/usr/local/lib", python / "lib", symlinks=True,
                    ignore=shutil.ignore_patterns("*.a", "*.o", "config-*", "__pycache__", "*.pyc", "site-packages", "pkgconfig"))
    for directory in (python / "lib").glob("python*/lib-dynload"):
        for file in directory.iterdir():
            if file.name.startswith(OMITTED):
                file.unlink()
    for directory in (python / "lib").glob("python*"):
        for name in ("ensurepip", "idlelib", "tkinter", "turtledemo"):
            shutil.rmtree(directory / name, ignore_errors=True)
    for name in ("python", "python3", "python3.12"):
        copy(Path("/usr/local/bin") / name, root)
    shutil.copytree("/opt/venv", root / "opt/venv", symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    artifacts = [Path("/") / file.relative_to(root) for file in root.rglob("*") if file.is_file()]
    libraries = closure(artifacts)
    system = {file for file in libraries if not str(file).startswith(("/usr/local/", "/opt/venv/"))}
    for file in sorted(libraries):
        copy(file, root)
    for name in ("/etc/os-release", "/etc/debian_version", "/etc/ssl/certs/ca-certificates.crt", "/etc/nsswitch.conf"):
        copy(Path(name), root)
    (root / "usr/lib/ssl").mkdir(parents=True, exist_ok=True)
    (root / "usr/lib/ssl/cert.pem").symlink_to("/etc/ssl/certs/ca-certificates.crt")
    inventory(root, system, Path("/var/lib/dpkg"))
    (root / "etc/passwd").write_text("hmt:x:10001:10001:HMT runtime:/data:/nonexistent\n")
    (root / "etc/group").write_text("hmt:x:10001:\n")
    for name in ("data", "run/hmt-scratch", "tmp"):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o1777 if name == "tmp" else 0o755)
        if name != "tmp":
            shutil.chown(directory, user=10001, group=10001)


if __name__ == "__main__":
    assemble(Path("/runtime-root"))
