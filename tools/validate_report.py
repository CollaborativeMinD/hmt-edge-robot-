"""validate: report interface."""

from __future__ import annotations

import json
import sqlite3

import polars as pl
from validate_base import EVIDENCE
from validate_incidents import external_gates, incidents
from validate_regression import junit_cases

from hmt_edge_robot.contracts import utc_now


def finalize(db: sqlite3.Connection, passed: bool) -> None:
    incidents(db)
    external_gates(db)
    queries = {
        "cumulative_gate_ledger": "SELECT * FROM cumulative_gate_ledger",
        "reverse_rca_ledger": "SELECT * FROM reverse_rca_ledger",
    }
    for table, query in queries.items():
        frame = pl.read_database(query, db)
        frame.write_csv(EVIDENCE / (table + ".csv"))
        frame.write_parquet(EVIDENCE / (table + ".parquet"))
    coverage = json.loads((EVIDENCE / "coverage.json").read_text())["totals"]
    report = {
        "timestamp_utc": utc_now(),
        "software_status": "PASS" if passed else "FAIL",
        "external_deployment_status": "HOLD",
        "coverage": coverage,
        "gate_columns": 7,
        "rrca_columns": 7,
        "ledger_semantics": "append-only observations; current run retests all software gates",
    }
    report["test_cases"] = len(junit_cases(EVIDENCE / "tests.xml"))
    (EVIDENCE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    db.close()
