"""usea: manifest interface."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .contracts import Effect


def file_manifest(root: Path, max_files: int = 256, max_bytes: int = 16_777_216) -> dict[str, str]:
    """Bounded regular-file snapshot; cannot observe reads, transient writes, sockets or processes."""
    if (
        type(max_files) is not int
        or not 1 <= max_files <= 1024
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= 16_777_216
    ):
        raise ValueError("MANIFEST_BOUNDS_INVALID")
    root = root.resolve(strict=True)
    result, total, visited = {}, 0, 0
    import os
    import stat

    # Directory descriptors anchor traversal; final open refuses links and special files.
    for directory, dirs, files, descriptor in os.fwalk(root, follow_symlinks=False):
        for name in dirs + files:
            visited += 1
            info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if visited > max_files * 2 or stat.S_ISLNK(info.st_mode):
                raise ValueError("MANIFEST_INCOMPLETE")
        for name in sorted(files):
            if len(result) >= max_files:
                raise ValueError("MANIFEST_INCOMPLETE")
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError("MANIFEST_INCOMPLETE")
                data = handle.read(max_bytes - total + 1)
            total += len(data)
            if total > max_bytes:
                raise ValueError("MANIFEST_BYTE_BOUND_EXCEEDED")
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return result

def manifest_effects(before: dict[str, str], after: dict[str, str]) -> tuple[Effect, ...]:
    if len(before) > 256 or len(after) > 256:
        raise ValueError("MANIFEST_DIFF_BOUND_EXCEEDED")
    return tuple(
        Effect(kind="write", target=path)
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
    )
