"""Repository boundary and debris checks."""

from __future__ import annotations

from pathlib import Path

from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus
from .shape_paths import defects

REQUIRED = (
    "README.md",
    "Start_here.md",
    "Index.md",
    "Runbook.md",
    "Agents.md",
    "pyproject.toml",
    "scaffold.policy.json",
    "architecture",
    "contracts",
    "src",
    "tests",
)


def run(root: Path, out: Path) -> LaneReport:
    findings = _missing(root) + defects(root, out)
    if findings:
        codes = tuple(item.reason_code for item in findings)
        return lane("repository-shape", LaneStatus.FAIL, "local", codes, tuple(findings))
    return lane("repository-shape", LaneStatus.PASS, "local", ("PASS_REPOSITORY_SHAPE",))


def _missing(root: Path) -> list[Finding]:
    return [
        Finding(
            reason_code="FAIL_REPOSITORY_SHAPE",
            message="Required boundary item is absent.",
            path=name,
        )
        for name in REQUIRED
        if not (root / name).exists()
    ]
