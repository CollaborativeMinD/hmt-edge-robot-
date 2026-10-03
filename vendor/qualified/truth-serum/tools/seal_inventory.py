from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

SEAL = "REPOSITORY_SEAL.json"
RUNTIME = "evidence/runtime"
SKIP_DIRS = {".git"}
DEBRIS_NAMES = {
    ".DS_Store",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}
LEDGER_TOKENS = ("checksum", "hash_ledger", "manifest.sha256")


def files(repo: Path) -> list[Path]:
    found: list[Path] = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(names):
            path = Path(root) / name
            relative = path.relative_to(repo).as_posix()
            if relative != SEAL and not relative.startswith(f"{RUNTIME}/"):
                found.append(path)
    return sorted(found, key=lambda path: path.relative_to(repo).as_posix())


def inventory(repo: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    byte_count = 0
    items = files(repo)
    for path in items:
        relative = path.relative_to(repo).as_posix()
        body = path.read_bytes()
        file_hash = hashlib.sha256(body).hexdigest()
        digest.update(f"{relative}\0{len(body)}\0{file_hash}\n".encode())
        byte_count += len(body)
    return digest.hexdigest(), len(items), byte_count


def preflight(repo: Path, allow_runtime: bool = False) -> list[str]:
    issues: set[str] = set()
    seen: dict[str, str] = {}
    for path in repo.rglob("*"):
        relative = path.relative_to(repo).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_symlink():
            issues.add(f"symlink:{relative}")
            continue
        in_runtime = relative == RUNTIME or relative.startswith(f"{RUNTIME}/")
        if in_runtime:
            if not allow_runtime:
                issues.add(f"debris:{RUNTIME}")
            continue
        if not (path.is_dir() or stat.S_ISREG(path.stat().st_mode)):
            issues.add(f"non-regular:{relative}")
        folded = relative.casefold()
        if folded in seen and seen[folded] != relative:
            issues.add(f"case-collision:{seen[folded]}:{relative}")
        seen[folded] = relative
        if any(part in DEBRIS_NAMES for part in path.relative_to(repo).parts):
            issues.add(f"debris:{relative}")
        is_ledger = any(token in path.name.lower() for token in LEDGER_TOKENS)
        if path.is_file() and relative != SEAL and is_ledger:
            issues.add(f"extra-checksum:{relative}")
    return sorted(issues)
