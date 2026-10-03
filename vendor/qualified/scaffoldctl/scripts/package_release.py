from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = "scaffoldctl"
ZIP_TIMESTAMP = (2026, 8, 3, 0, 0, 0)
EXCLUDED_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".git",
    "__pycache__",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(output: Path) -> tuple[Path, ...]:
    selected: list[Path] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise RuntimeError(f"symlink is not admitted to release: {relative.as_posix()}")
        if not path.is_file() or path.name == ".coverage" or path.resolve() == output:
            continue
        selected.append(path)
    return tuple(sorted(selected, key=lambda item: item.relative_to(ROOT).as_posix()))


def _checksum_map() -> dict[str, str]:
    checksum_path = ROOT / "evidence" / "SHA256SUMS"
    result: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        path = PurePosixPath(relative)
        if (
            separator != "  "
            or len(digest) != 64
            or path.is_absolute()
            or ".." in path.parts
            or relative in result
        ):
            raise RuntimeError("release checksum ledger is malformed")
        result[relative] = digest
    return result


def _verify_checksums(files: tuple[Path, ...]) -> None:
    expected = _checksum_map()
    observed = {
        path.relative_to(ROOT).as_posix(): _sha256(path)
        for path in files
        if path.relative_to(ROOT).as_posix() != "evidence/SHA256SUMS"
    }
    if observed != expected:
        raise RuntimeError("release files do not match the evidence checksum ledger")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _write_archive(output: Path, files: tuple[Path, ...]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for path in files:
                relative = path.relative_to(ROOT).as_posix()
                info = zipfile.ZipInfo(f"{PACKAGE_ROOT}/{relative}", ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                mode = 0o100755 if path.stat().st_mode & 0o111 else 0o100644
                info.external_attr = mode << 16
                archive.writestr(
                    info,
                    path.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        os.replace(temporary, output)
        directory = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _verify_archive(output: Path, files: tuple[Path, ...]) -> None:
    expected = {
        f"{PACKAGE_ROOT}/{path.relative_to(ROOT).as_posix()}": _sha256(path) for path in files
    }
    observed: dict[str, str] = {}
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"release archive failed CRC validation: {bad}")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or info.filename in observed:
                raise RuntimeError("release archive contains an unsafe or duplicate path")
            observed[info.filename] = hashlib.sha256(archive.read(info)).hexdigest()
    if observed != expected:
        raise RuntimeError("release archive contents differ from the source release set")


def main() -> int:
    output = _arguments().output.resolve()
    files = _files(output)
    _verify_checksums(files)
    _write_archive(output, files)
    _verify_archive(output, files)
    print(f"{_sha256(output)}  {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
