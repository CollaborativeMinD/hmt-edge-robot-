"""Evidence-claim reference and digest binding."""

from __future__ import annotations

import json
from pathlib import Path

from ..files import relative, repository_files
from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus
from .claim_contract import bind, load


def run(root: Path, out: Path) -> LaneReport:
    paths = [path for path in repository_files(root, out) if _claim_file(path)]
    if not paths:
        return lane(
            "evidence-binding",
            LaneStatus.NOT_APPLICABLE,
            "local",
            ("NOT_APPLICABLE_EVIDENCE_CLAIMS",),
        )
    findings = tuple(item for path in paths for item in _inspect(path, root))
    if findings:
        return lane(
            "evidence-binding",
            LaneStatus.FAIL,
            "local",
            tuple(x.reason_code for x in findings),
            findings,
        )
    return lane("evidence-binding", LaneStatus.PASS, "local", ("PASS_EVIDENCE_BINDING",))


def _claim_file(path: Path) -> bool:
    return (
        path.name == "claims.json"
        or path.name.endswith(".claims.json")
        or path.name.endswith(".evidence.jsonl")
    )


def _inspect(path: Path, root: Path) -> list[Finding]:
    rel = relative(path, root)
    try:
        claims = load(path)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return [Finding(reason_code="FAIL_EVIDENCE_CLAIM_SCHEMA", message=str(error), path=rel)]
    findings: list[Finding] = []
    for index, claim in enumerate(claims, start=1):
        findings.extend(bind(claim, root, index))
    return findings
