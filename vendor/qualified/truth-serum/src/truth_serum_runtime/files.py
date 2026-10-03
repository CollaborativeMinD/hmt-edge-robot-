"""Deterministic repository file discovery."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

SKIP_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def beneath(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def repository_files(root: Path, out: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            continue
        relative_parts = path.relative_to(root).parts
        if beneath(path, out) or any(part in SKIP_NAMES for part in relative_parts):
            continue
        if path.is_file():
            yield path


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)
