"""Lane construction and deterministic decision aggregation."""

from __future__ import annotations

from .models import Decision, Finding, LaneReport, LaneStatus


def lane(
    lane_id: str,
    status: LaneStatus,
    tool: str,
    codes: tuple[str, ...],
    findings: tuple[Finding, ...] = (),
    evidence: tuple[str, ...] = (),
    required: bool = True,
) -> LaneReport:
    return LaneReport(
        lane_id=lane_id,
        status=status,
        required=required,
        tool=tool,
        reason_codes=tuple(sorted(set(codes))),
        evidence_paths=tuple(sorted(set(evidence))),
        findings=findings,
    )


def aggregate(lanes: tuple[LaneReport, ...]) -> Decision:
    routes = {item.route for report in lanes for item in report.findings}
    if Decision.ESCALATE in routes:
        return Decision.ESCALATE
    if any(report.status is LaneStatus.FAIL for report in lanes):
        return Decision.FAIL
    blocked = {LaneStatus.UNAVAILABLE, LaneStatus.ERROR}
    if any(report.required and report.status in blocked for report in lanes):
        return Decision.HOLD
    return Decision.PASS


def reasons(lanes: tuple[LaneReport, ...]) -> tuple[str, ...]:
    return tuple(sorted({code for report in lanes for code in report.reason_codes}))
