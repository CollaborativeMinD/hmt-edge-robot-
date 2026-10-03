from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tests._support import (
    REPORT_FIELDS,
    ROOT,
    copy_release,
    report,
    run_admission,
    strict_json,
    stubbed_path,
    write,
)

EXPECTED_NUMBERS = tuple(f"{number:03d}" for number in range(1, 12))


class ContractAndTraceTests(unittest.TestCase):
    def test_generated_report_and_trace_validate_against_closed_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            result = run_admission(
                repo,
                "architecture-only",
                path=stubbed_path(base / "bin"),
                attempt_id="schema-attempt-001",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = report(repo)
            self.assertEqual(set(payload), REPORT_FIELDS)
            report_schema = strict_json(repo / "contracts/schemas/admission_report.schema.json")
            lane_schema = strict_json(repo / "contracts/schemas/lane_result.schema.json")
            trace_schema = strict_json(repo / "contracts/schemas/admission_trace.schema.json")
            Draft202012Validator.check_schema(report_schema)
            Draft202012Validator(report_schema).validate(payload)
            for lane in payload["lanes"]:
                Draft202012Validator(lane_schema).validate(lane)
            trace_path = repo / "evidence/runtime/admission_trace.jsonl"
            lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line]
            self.assertGreaterEqual(len(lines), 1)
            events = [json.loads(line, parse_constant=self._reject_constant) for line in lines]
            validator = Draft202012Validator(trace_schema)
            for event in events:
                validator.validate(event)
            self.assertEqual([item["sequence"] for item in events], list(range(len(events))))
            self.assertTrue(all(item["attempt_id"] == "schema-attempt-001" for item in events))
            self.assertTrue(all(item["mode"] == "architecture-only" for item in events))

    def test_report_schema_is_exact_new_contract_without_legacy_seal_fields(self) -> None:
        schema = strict_json(ROOT / "contracts/schemas/admission_report.schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), REPORT_FIELDS)
        self.assertEqual(set(schema["properties"]), REPORT_FIELDS)
        self.assertEqual(
            set(schema["properties"]["decision"]["enum"]),
            {"PASS", "HOLD", "FAIL", "ESCALATE"},
        )
        retired = {
            "created_utc",
            "repo_root",
            "pace_t_state",
            "repository_pressure",
            "critical_slack",
            "manifest_sha256",
            "hash_ledger_sha256",
            "evidence_manifest_path",
        }
        self.assertTrue(retired.isdisjoint(schema["properties"]))

    def test_root_req_inv_oracle_thread_is_exactly_001_through_011(self) -> None:
        matrix = (ROOT / "architecture/requirements_traceability.md").read_text(encoding="utf-8")
        row_pattern = re.compile(
            r"^\| REQ-TS-(\d{3}) \| INV-TS-(\d{3}) \| .*? \| ORACLE-TS-(\d{3}) \|",
            re.MULTILINE,
        )
        rows = row_pattern.findall(matrix)
        self.assertEqual(len(rows), 11)
        self.assertEqual(tuple(requirement for requirement, _, _ in rows), EXPECTED_NUMBERS)
        self.assertEqual(tuple(invariant for _, invariant, _ in rows), EXPECTED_NUMBERS)
        self.assertEqual(tuple(oracle for _, _, oracle in rows), EXPECTED_NUMBERS)
        self.assertTrue(
            all(requirement == invariant == oracle for requirement, invariant, oracle in rows)
        )
        invariants = (ROOT / "architecture/mission_invariants.md").read_text(encoding="utf-8")
        invariant_rows = tuple(re.findall(r"^\| INV-TS-(\d{3}) \|", invariants, re.MULTILINE))
        oracle_rules = tuple(re.findall(r"^- ORACLE-TS-(\d{3}):", matrix, re.MULTILINE))
        self.assertEqual(invariant_rows, EXPECTED_NUMBERS)
        self.assertEqual(oracle_rules, EXPECTED_NUMBERS)

    def test_policy_authority_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            policy = repo / "contracts/lane_policy.yaml"
            content = policy.read_text(encoding="utf-8").replace(
                "blocking_finding: FAIL", "blocking_finding: PASS"
            )
            write(policy, content)
            result = run_admission(repo, "architecture-only", path=stubbed_path(base / "bin"))
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("FAIL_ARCHITECTURE_POLICY_MISMATCH", str(report(repo)))

    @staticmethod
    def _reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")


if __name__ == "__main__":
    unittest.main()
