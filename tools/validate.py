"""Compatibility facade for the decomposed validate interfaces."""

from __future__ import annotations

import asyncio
import json
import sys

from validate_base import EVIDENCE as EVIDENCE
from validate_base import ROOT as ROOT
from validate_base import RUN as RUN
from validate_base import sha as sha
from validate_execution import execute as execute
from validate_incidents import external_gates as external_gates
from validate_incidents import incidents as incidents
from validate_ledger import database as database
from validate_ledger import record as record
from validate_regression import junit_cases as junit_cases
from validate_regression import regression_groups as regression_groups
from validate_report import finalize as finalize
from validate_structure import ontology_checks as ontology_checks
from validate_structure import structural_checks as structural_checks


async def main() -> None:
    db = database()
    commands = [
        ("G-APPLIANCE-DESIGN-022", "REQ-APPLIANCE-01/02/03", [sys.executable, "tools/appliance_design.py"]),
        ("G-CI-013", "REQ-CI-01", [sys.executable, "tools/ci_admission.py"]),
        ("G-POLICY-014", "REQ-CI2-01", [sys.executable, "tools/policy_evaluation.py"]),
        ("G-ARTIFACT-DESIGN-019", "REQ-CD4-01", [sys.executable, "tools/artifact_design.py"]),
        ("G-ARTIFACT-NEGATIVE-020", "REQ-CD4-03/04", [sys.executable, "tools/artifact_campaign.py"]),
        ("G-CD-CONTRACT-017", "REQ-CD3-01/02", [sys.executable, "tools/deployment_gate.py"]),
        ("G-CD-NEGATIVE-018", "REQ-CD3-03/04", [sys.executable, "tools/deployment_campaign.py"]),
        ("G-PROFILE-015", "REQ-CI2-02", [sys.executable, "tools/ci_profiles.py"]),
        ("G-QUALIFY-016", "REQ-CI2-03", [sys.executable, "tools/tool_qualification.py"]),
        ("G-TYPES-012", "REQ-NFR-11", ["pyrefly", "check", "--min-severity", "warn"]),
        ("G-STATIC-007", "REQ-NFR-07", ["ruff", "check", "src", "tests", "tools", "notebooks"]),
        (
            "G-RUNTIME-004",
            "ALL_FUNCTIONAL/REQ-NFR-10",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--cov=hmt_edge_robot",
                "--cov-report=json:evidence/coverage.json",
                "--junitxml=evidence/tests.xml",
            ],
        ),
        ("G-PERF-006", "REQ-NFR-06", [sys.executable, "tools/coupled_campaign.py"]),
        ("G-TRIAD-011", "REQ-SAT-NFR-06", [sys.executable, "tools/assurance_campaign.py"]),
        (
            "G-NOTEBOOK-008",
            "REQ-SYS-01",
            ["marimo", "export", "html", "notebooks/cell_ssot.py", "-o", "evidence/cell_ssot.html"],
        ),
    ]
    results = [await execute(db, gate, requirement, args) for gate, requirement, args in commands]
    try:
        result = structural_checks()
    except Exception as exc:
        result = {"status": "FAIL", "reason": str(exc)}
    path = RUN / "structural_checks.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    record(db, "G-ARCH-001", "REQ-NFR-07/08", result["status"], path)
    passed = all(results) and result["status"] == "PASS" and regression_groups(db)
    finalize(db, passed)
    if not passed:
        raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(main())
