"""validate: ledger interface."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from validate_base import EVIDENCE, ROOT, RUN, sha

from hmt_edge_robot.contracts import utc_now


def database() -> sqlite3.Connection:
    EVIDENCE.mkdir(exist_ok=True)
    RUN.mkdir(parents=True)
    db = sqlite3.connect(EVIDENCE / "verification.sqlite")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS cumulative_gate_ledger (
        timestamp TEXT, task TEXT, gate_id TEXT, requirement TEXT, status TEXT,
        evidence_ref TEXT, evidence_hash_reason TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reverse_rca_ledger (
        timestamp TEXT, incident_id TEXT, checkpoint TEXT, observed_state TEXT,
        causal_evidence TEXT, validation_test TEXT, disposition TEXT)""")
    return db

def record(db: sqlite3.Connection, gate: str, requirement: str, status: str, path: Path) -> None:
    db.execute(
        "INSERT INTO cumulative_gate_ledger VALUES (?,?,?,?,?,?,?)",
        (
            utc_now(),
            "OBJ-EDGE-01/cumulative",
            gate,
            requirement,
            status,
            str(path.relative_to(ROOT)),
            sha(path),
        ),
    )
    db.commit()
