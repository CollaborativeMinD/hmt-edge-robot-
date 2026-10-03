"""Evidence-output authority and fresh-attempt preparation."""

from __future__ import annotations

import shutil
from pathlib import Path


def resolve(root: Path, requested: Path) -> Path:
    candidate = requested if requested.is_absolute() else root / requested
    _reject_symlinks(root, candidate)
    output = candidate.resolve()
    try:
        relative = output.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("--out must remain beneath --repo") from error
    if len(relative.parts) < 2 or relative.parts[0] != "evidence":
        raise ValueError("--out must be a child of the evidence directory")
    if not relative.name.startswith("runtime"):
        raise ValueError("--out leaf must start with runtime")
    if output.exists() and not output.is_dir():
        raise ValueError("--out must be a directory or an absent path")
    return output


def prepare(root: Path, requested: Path) -> Path:
    output = resolve(root, requested)
    if output.exists():
        _reject_symlinks(root, output)
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=False)
    return output


def _reject_symlinks(root: Path, candidate: Path) -> None:
    absolute = candidate if candidate.is_absolute() else root / candidate
    cursor = root.resolve()
    try:
        relative = absolute.absolute().relative_to(cursor)
    except ValueError:
        return
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("--out may not traverse a symlink")
    if absolute.exists() and absolute.is_dir() and any(
        path.is_symlink() for path in absolute.rglob("*")
    ):
        raise ValueError("--out contains a symlink")
