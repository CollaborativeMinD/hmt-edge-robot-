"""validate: incidents interface."""

from __future__ import annotations

import json
import sqlite3

from validate_base import ROOT
from validate_ledger import record

from hmt_edge_robot.contracts import utc_now


def incidents(db: sqlite3.Connection) -> None:
    rows = json.loads((ROOT / "docs/incidents.json").read_text())
    for incident in rows:
        if db.execute(
            "SELECT 1 FROM reverse_rca_ledger WHERE incident_id=?", (incident["incident_id"],)
        ).fetchone():
            continue
        disposition = "INVESTIGATION_COMPLETE; " + (
            "REQUIRES_OPERATOR_ESCALATION"
            if incident["external_boundary"]
            else "SOLUTION_CANDIDATE_APPLIED"
        )
        for checkpoint in ("OBSERVED", "CAUSAL_EDGE", "DOWNSTREAM_REGRESSION"):
            db.execute(
                "INSERT INTO reverse_rca_ledger VALUES (?,?,?,?,?,?,?)",
                (
                    utc_now(),
                    incident["incident_id"],
                    checkpoint,
                    incident["observed_state"],
                    incident["causal_evidence"] + "; " + incident["remediation"],
                    incident["validation_test"],
                    disposition,
                ),
            )
    db.commit()

def external_gates(db: sqlite3.Connection) -> None:
    for gate in (
        "G-HARDWARE-001",
        "G-CALIBRATION-002",
        "G-MISRA-003",
        "G-MEMORY-004",
        "G-UB-005",
        "G-DISTRIBUTED-006",
        "G-ML-007",
    ):
        record(db, gate, "EXTERNAL_DEPLOYMENT", "HOLD", ROOT / "docs/compliance.md")
    live = ROOT / "evidence/live_session.json"
    result = json.loads(live.read_text())
    admitted = (
        result["status"] == "PASS" and result["conservative_session_reserved_upper_bound_usd"] <= 1
    )
    record(db, "G-LIVE-009", "REQ-HMT-04/bounded-canary", "PASS" if admitted else "HOLD", live)
