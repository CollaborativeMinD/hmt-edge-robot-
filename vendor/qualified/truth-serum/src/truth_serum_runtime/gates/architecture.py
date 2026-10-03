"""Architecture-to-requirement trace checks."""

from __future__ import annotations

import re
from pathlib import Path

from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus
from ..policy import PolicyError
from ..policy import read as read_policy

REQUIRED = (
    "architecture/mission_invariants.md",
    "architecture/reason_codes.json",
    "architecture/requirements_traceability.md",
    "architecture/truth_serum.sysml",
    "contracts/lane_policy.yaml",
    "contracts/schemas/admission_report.schema.json",
    "contracts/schemas/admission_trace.schema.json",
    "contracts/schemas/evidence_claim.schema.json",
    "contracts/schemas/lane_result.schema.json",
    "contracts/schemas/machine_handoff.schema.json",
)


def run(root: Path, _out: Path) -> LaneReport:
    missing = tuple(name for name in REQUIRED if not (root / name).is_file())
    findings = [
        Finding(
            reason_code="FAIL_ARCHITECTURE_TRACE_MISSING",
            message="Required trace artifact is absent.",
            path=name,
        )
        for name in missing
    ]
    if not missing:
        findings.extend(_trace_defects(root))
        findings.extend(_policy_defects(root))
    if findings:
        codes = tuple(item.reason_code for item in findings)
        return lane("architecture-trace", LaneStatus.FAIL, "local", codes, tuple(findings))
    return lane("architecture-trace", LaneStatus.PASS, "local", ("PASS_ARCHITECTURE_TRACE",))


def _trace_defects(root: Path) -> list[Finding]:
    rtm = (root / "architecture/requirements_traceability.md").read_text(encoding="utf-8")
    invariants = (root / "architecture/mission_invariants.md").read_text(encoding="utf-8")
    sysml = (root / "architecture/truth_serum.sysml").read_text(encoding="utf-8")
    findings: list[Finding] = []
    for prefix, documents in (
        ("REQ", (rtm, sysml)),
        ("INV", (rtm, invariants)),
        ("ORACLE", (rtm, sysml)),
    ):
        expected = {f"{prefix}-TS-{number:03d}" for number in range(1, 12)}
        for label, content in zip(("trace", "authority"), documents, strict=True):
            actual = set(re.findall(rf"\b{prefix}-TS-\d{{3}}\b", content))
            if actual != expected:
                findings.append(
                    Finding(
                        reason_code="FAIL_ARCHITECTURE_TRACE_UNBOUND",
                        message=f"{label} {prefix} identifiers are not exactly 001..011.",
                    )
                )
    return findings


def _policy_defects(root: Path) -> list[Finding]:
    try:
        read_policy(root / "contracts/lane_policy.yaml")
    except PolicyError as error:
        return [
            Finding(
                reason_code="FAIL_ARCHITECTURE_POLICY_MISMATCH",
                message=str(error),
                path="contracts/lane_policy.yaml",
            )
        ]
    return []
