"""Canonical report and admission-trace serialization."""

from __future__ import annotations

import json
from pathlib import Path

from .files import write_text
from .models import AdmissionReport, LaneReport


def write(report: AdmissionReport, out: Path) -> None:
    payload = report.model_dump(mode="json")
    write_text(out / "admission_report.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    records = [_event(report, item, sequence) for sequence, item in enumerate(report.lanes)]
    trace = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records
    )
    write_text(out / "admission_trace.jsonl", trace)


def _event(
    report: AdmissionReport,
    lane: LaneReport,
    sequence: int,
) -> dict[str, object]:
    artifacts = [
        {"path": path, "kind": "WITNESS_OUTPUT", "state": "PRESENT"} for path in lane.evidence_paths
    ]
    evidence = [{"path": path, "evidence_class": "RAW_WITNESS"} for path in lane.evidence_paths]
    return {
        "schema_id": "truth_serum.admission_trace_event",
        "schema_version": "1.0.0",
        "attempt_id": report.attempt_id,
        "sequence": sequence,
        "mode": report.mode.value,
        "stage": lane.lane_id,
        "artifacts": artifacts,
        "transition": {"from": "PENDING", "to": lane.status.value},
        "reason_codes": list(lane.reason_codes),
        "evidence": evidence,
    }
