"""Repository path defect discovery."""

from __future__ import annotations

from pathlib import Path

from ..files import beneath, relative
from ..models import Decision, Finding

DEBRIS = {
    ".DS_Store",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def defects(root: Path, out: Path) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        rel = relative(path, root)
        if path.is_symlink():
            findings.append(_symlink(rel))
            continue
        if beneath(path, out):
            continue
        folded = rel.casefold()
        if folded in seen and seen[folded] != rel:
            findings.append(
                Finding(
                    reason_code="FAIL_REPOSITORY_CASE_COLLISION",
                    message=f"Case-fold collision with {seen[folded]}.",
                    path=rel,
                )
            )
        seen[folded] = rel
        findings.extend(_name_defects(path, rel))
    return findings


def _name_defects(path: Path, rel: str) -> list[Finding]:
    name = path.name.lower()
    findings: list[Finding] = []
    if (
        path.name in DEBRIS
        or name.endswith(".sha256")
        or "hash_ledger" in name
        or "checksum" in name
    ):
        findings.append(
            Finding(
                reason_code="FAIL_REPOSITORY_SHAPE",
                message="Development debris or obsolete digest ledger.",
                path=rel,
            )
        )
    if " " in path.name or path.name.startswith(".."):
        findings.append(
            Finding(
                reason_code="FAIL_REPOSITORY_SHAPE",
                message="Path name is not CLI-safe.",
                path=rel,
            )
        )
    allowed_python = (
        rel == "truth_serum.py"
        or rel.startswith("src/")
        or rel.startswith("tools/")
        or rel.startswith("tests/")
    )
    if path.is_file() and path.suffix == ".py" and not allowed_python:
        findings.append(
            Finding(
                reason_code="FAIL_REPOSITORY_SHAPE",
                message="Python source is outside an admissible source or test region.",
                path=rel,
            )
        )
    return findings


def _symlink(rel: str) -> Finding:
    return Finding(
        reason_code="ESCALATE_REPOSITORY_SYMLINK_ESCAPE",
        message="Symlinks are prohibited at the repository boundary.",
        path=rel,
        route=Decision.ESCALATE,
    )
