"""validate: regression interface."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from defusedxml import ElementTree as ET
from validate_base import EVIDENCE, ROOT, RUN
from validate_ledger import record


def junit_cases(path: Path) -> list:
    root = ET.parse(path).getroot()
    if root is None:
        raise ValueError("JUNIT_ROOT_MISSING")
    return root.findall(".//testcase")

def regression_groups(db: sqlite3.Connection) -> bool:
    path = RUN / "tests.xml"
    path.write_bytes((EVIDENCE / "tests.xml").read_bytes())
    cases = junit_cases(path)
    outcomes = {}
    for case in cases:
        name = case.attrib["name"].split("[")[0]
        passed = not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
        outcomes[name] = outcomes.get(name, True) and passed
    groups = {
        "G-SCHEMA-002": [
            "test_contracts_forbid_unknown_mutation_coercion",
            "test_nonfinite_boundary_rejected",
        ],
        "G-AUTH-003": [
            "test_access_auth_scope_expiry_and_revocation",
            "test_global_body_and_rate_bounds",
            "test_authority_rechecked_after_movement",
            "test_routed_model_id_and_stop_admission",
        ],
        "G-REPLAY-005": [
            "test_ledger_corruption_detected",
            "test_projection_tamper_detected",
            "test_read_only_queries_do_not_recover_pending_tasks",
        ],
    }
    requirements = json.loads((ROOT / "docs/requirements.json").read_text())["requirements"]
    groups["G-REQUIREMENTS-010"] = [r["tests"][0].split("::")[1] for r in requirements]
    results = []
    for gate, names in groups.items():
        passed = all(outcomes.get(name, False) for name in names)
        record(db, gate, "OBJ-EDGE-01/regression-binding", "PASS" if passed else "FAIL", path)
        results.append(passed)
    return all(results)
