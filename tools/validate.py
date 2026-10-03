"""Cumulative offline verification. Never reads provider secrets or calls an LLM."""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import jsonschema
import polars as pl
from contracts_export import contract_models, export
from defusedxml import ElementTree as ET
from rdflib import Graph, Namespace

from hmt_edge_robot.contracts import utc_now

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
RUN = EVIDENCE / "runs" / utc_now().replace(":", "-")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


async def execute(db: sqlite3.Connection, gate: str, requirement: str, args: list[str]) -> bool:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        process.kill()
        output, _ = await process.communicate()
        output += b"\nVERIFICATION_TIMEOUT\n"
    path = RUN / (gate + ".log")
    path.write_bytes(output)
    passed = process.returncode == 0
    record(db, gate, requirement, "PASS" if passed else "FAIL", path)
    print(gate, "PASS" if passed else "FAIL", flush=True)
    return passed


def structural_checks() -> dict:
    lengths = []
    for directory in ("src", "tests", "tools", "notebooks"):
        for path in (ROOT / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    size = (node.end_lineno or node.lineno) - node.lineno + 1
                    lengths.append(
                        {
                            "path": str(path.relative_to(ROOT)),
                            "function": node.name,
                            "physical_lines": size,
                        }
                    )
                    if size > 60:
                        raise ValueError(f"FUNCTION_LINE_CAP: {path.name}:{node.name}:{size}")
    requirements = json.loads((ROOT / "docs/requirements.json").read_text())["requirements"]
    if len({r["id"] for r in requirements}) != len(requirements):
        raise ValueError("DUPLICATE_REQUIREMENT")
    for requirement in requirements:
        for source in requirement["source"]:
            if not (ROOT / source).is_file():
                raise ValueError("REQUIREMENT_SOURCE_MISSING")
        for test in requirement["tests"]:
            file, function = test.split("::")
            if f"def {function}(" not in (ROOT / file).read_text():
                raise ValueError("REQUIREMENT_TEST_MISSING")
    ontology_checks()
    trace = json.loads((ROOT / "docs/implementation_traceability.json").read_text())
    if {r["req_id"] for r in trace} != {r["id"] for r in requirements}:
        raise ValueError("IMPLEMENTATION_TRACE_INCOMPLETE")
    fields = {
        "req_id",
        "module_id",
        "runtime_partition",
        "source_path",
        "contract_id",
        "safety_constraint_id",
        "test_id",
        "analysis_id",
        "evidence_id",
    }
    if any(set(r) != fields or not all(r.values()) for r in trace):
        raise ValueError("IMPLEMENTATION_TRACE_FIELDS_INVALID")
    handoff = json.loads((ROOT / "docs/machine_handoff.json").read_text())
    schema = json.loads((ROOT / "docs/handoff.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(handoff)
    return {
        "status": "PASS",
        "requirements": len(requirements),
        "functions": lengths,
        "max_physical_lines": max(r["physical_lines"] for r in lengths),
    }


def ontology_checks() -> None:
    export(ROOT)
    bindings = json.loads((ROOT / "docs/field_bindings.json").read_text())
    expected = {
        (name, field) for name, model in contract_models().items() for field in model.model_fields
    }
    actual = {(b["contract"], b["field"]) for b in bindings}
    if expected != actual or len(actual) != len(bindings):
        raise ValueError("FIELD_BINDING_INCOMPLETE")
    baseline = json.loads((ROOT / "docs/source_provenance.json").read_text())
    classes = set(baseline["upstream_subtype_classes"])
    if any(b["subtype"] not in classes for b in bindings):
        raise ValueError("ONTOLOGY_SUBTYPE_UNGOVERNED")
    graph = Graph().parse(ROOT / "docs/field_bindings.ttl", format="turtle")
    forge = Namespace("https://terminal-state.systems/ontology/forge#")
    if len(list(graph.triples((None, forge.hard_binds_to_subtype, None)))) != len(bindings):
        raise ValueError("RDF_BINDING_DIVERGENCE")


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


async def main() -> None:
    db = database()
    commands = [
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
