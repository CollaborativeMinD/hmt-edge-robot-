"""Admission orchestration without release-seal authority."""

from __future__ import annotations

from pathlib import Path

from . import gates
from .evidence import write
from .external import run_all
from .lanes import aggregate, reasons
from .models import AdmissionMode, AdmissionReport, Decision, RepositoryPosture
from .output import prepare

FINAL_POSTURE = {
    Decision.PASS: RepositoryPosture.PRIMARY,
    Decision.HOLD: RepositoryPosture.ALTERNATE,
    Decision.FAIL: RepositoryPosture.EMERGENCY,
    Decision.ESCALATE: RepositoryPosture.TERMINAL,
}


def admit(
    root: Path,
    out: Path,
    mode: AdmissionMode,
    attempt_id: str,
) -> AdmissionReport:
    resolved_root = root.resolve()
    resolved_out = prepare(resolved_root, out)
    local = (
        gates.architecture_trace(resolved_root, resolved_out),
        gates.repository_shape(resolved_root, resolved_out),
        gates.source_aperture(resolved_root, resolved_out),
        gates.structured_data(resolved_root, resolved_out),
        gates.evidence_binding(resolved_root, resolved_out),
        gates.secret_scan(resolved_root, resolved_out),
        gates.shell_syntax(resolved_root, resolved_out),
    )
    lanes = local + run_all(mode, resolved_root, resolved_out)
    decision = aggregate(lanes)
    report = AdmissionReport(
        attempt_id=attempt_id,
        mode=mode,
        decision=decision,
        posture=FINAL_POSTURE[decision],
        clear=decision.value == "PASS",
        reasons=reasons(lanes),
        lanes=lanes,
        evidence_dir=resolved_out.relative_to(resolved_root).as_posix(),
        policy_path="contracts/lane_policy.yaml",
    )
    write(report, resolved_out)
    return report
