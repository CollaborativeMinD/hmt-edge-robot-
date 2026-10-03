from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests._support import copy_release, report, report_text, run_admission, stubbed_path, write


class RepositoryGateTests(unittest.TestCase):
    def assert_decision_with(
        self,
        repo: Path,
        base: Path,
        reason: str,
        evidence: str,
        *,
        decision: str = "FAIL",
        exit_code: int = 1,
    ) -> None:
        result = run_admission(repo, "architecture-only", path=stubbed_path(base / "bin"))
        self.assertEqual(result.returncode, exit_code, result.stderr)
        payload = report(repo)
        self.assertEqual(payload["decision"], decision)
        rendered = report_text(payload)
        self.assertIn(reason, rendered)
        self.assertIn(evidence, rendered)

    def test_python_function_over_sixty_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            lines = ["def oversized_function():"]
            lines.extend(f"    value_{number} = {number}" for number in range(60))
            lines.append("    return value_59")
            write(repo / "src/oversized_function.py", "\n".join(lines) + "\n")
            self.assert_decision_with(
                repo, base, "FAIL_SOURCE_FUNCTION_APERTURE", "oversized_function.py"
            )

    def test_python_module_at_one_hundred_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            body = "\n".join(f"VALUE_{number} = {number}" for number in range(100)) + "\n"
            write(repo / "src/hundred_line_module.py", body)
            self.assert_decision_with(
                repo, base, "FAIL_SOURCE_MODULE_APERTURE", "hundred_line_module.py"
            )

    def test_duplicate_json_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            write(repo / "config/duplicate.json", '{"guard": true, "guard": false}\n')
            self.assert_decision_with(repo, base, "FAIL_JSON_DUPLICATE_KEY", "duplicate.json")

    def test_nonfinite_json_number_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            write(repo / "config/nonfinite.json", '{"pressure": NaN}\n')
            self.assert_decision_with(repo, base, "FAIL_JSON_NONFINITE", "nonfinite.json")

    def test_duplicate_yaml_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            write(repo / "config/duplicate.yaml", "guard: true\nguard: false\n")
            self.assert_decision_with(repo, base, "FAIL_YAML_DUPLICATE_KEY", "duplicate.yaml")

    def test_secret_material_fails_security_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            key_name = "API_" + "KEY"
            key_value = "sk-test-" + "0123456789abcdefghijklmnop"
            write(repo / ".env", f'{key_name}="{key_value}"\n')
            self.assert_decision_with(
                repo,
                base,
                "ESCALATE_SECRET_EXPOSURE",
                ".env",
                decision="ESCALATE",
                exit_code=4,
            )

    def test_unquoted_qualified_secret_fails_security_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            key_name = "OPENAI_API_" + "KEY"
            key_value = "sk-" + "proj-0123456789abcdefghijklmnopqrstuv"
            write(repo / "config/credentials.txt", f"{key_name}={key_value}\n")
            self.assert_decision_with(
                repo,
                base,
                "ESCALATE_SECRET_EXPOSURE",
                "credentials.txt",
                decision="ESCALATE",
                exit_code=4,
            )

    def test_shell_syntax_error_fails_shell_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            write(repo / "scripts/broken.sh", "#!/bin/sh\nif true; then\n  echo broken\n")
            self.assert_decision_with(repo, base, "FAIL_SHELL_SYNTAX", "broken.sh")

    def test_commented_or_late_strict_mode_fails_shell_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            write(
                repo / "scripts/comment_bypass.sh",
                "#!/usr/bin/env bash\n"
                "# set -euo pipefail\n"
                "printf 'unsafe first\\n'\n"
                "set -euo pipefail\n",
            )
            self.assert_decision_with(
                repo,
                base,
                "FAIL_SHELL_STRICT_MODE",
                "comment_bypass.sh",
            )

    def test_claim_binding_recomputes_bytes_and_rejects_one_byte_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            target = repo / "README.md"
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            claims = {
                "claims": [
                    {
                        "claim_id": "CLAIM-ACCEPTANCE-001",
                        "statement": "README bytes are bound to this claim.",
                        "file_path": "README.md",
                        "sha256": digest,
                    }
                ]
            }
            write(repo / "evidence/claims.json", json.dumps(claims) + "\n")
            path = stubbed_path(base / "bin")
            first = run_admission(repo, "architecture-only", path=path)
            self.assertEqual(first.returncode, 0, first.stderr)
            target.write_bytes(target.read_bytes() + b"\n")
            second = run_admission(repo, "architecture-only", path=path)
            self.assertEqual(second.returncode, 1, second.stderr)
            payload = report(repo)
            self.assertEqual(payload["decision"], "FAIL")
            self.assertIn("FAIL_EVIDENCE_HASH_MISMATCH", report_text(payload))
            self.assertIn("README.md", report_text(payload))

    def test_claim_boundary_rejects_unknown_and_nonfinite_fields(self) -> None:
        mutations = {
            "unknown-field": (
                '{"claim_id":"CLAIM-STRICT-001","statement":"bounded",'
                '"file_path":"README.md","sha256":"' + "0" * 64 + '","authority":"human"}\n'
            ),
            "nonfinite": (
                '{"claim_id":"CLAIM-STRICT-001","statement":NaN,'
                '"file_path":"README.md","sha256":"' + "0" * 64 + '"}\n'
            ),
            "invalid-path-character": (
                '{"claim_id":"CLAIM-STRICT-001","statement":"bounded",'
                '"file_path":"fixtures/proof@1.txt","sha256":"' + "0" * 64 + '"}\n'
            ),
        }
        for name, claim in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                write(repo / "evidence/probe.evidence.jsonl", claim)
                self.assert_decision_with(
                    repo,
                    base,
                    "FAIL_EVIDENCE_CLAIM_SCHEMA",
                    "probe.evidence.jsonl",
                )

    def test_repository_shape_rejects_extra_ledgers_caches_and_case_collisions(self) -> None:
        mutations = {
            "extra-ledger": (
                lambda repo: write(repo / "rogue_checksum.txt", "obsolete\n"),
                "FAIL_REPOSITORY_SHAPE",
                "rogue_checksum.txt",
            ),
            "cache-debris": (
                lambda repo: write(repo / ".ruff_cache/sentinel", "debris\n"),
                "FAIL_REPOSITORY_SHAPE",
                ".ruff_cache",
            ),
            "case-collision": (
                self._case_collision,
                "FAIL_REPOSITORY_CASE_COLLISION",
                "collisionprobe.txt",
            ),
        }
        for name, (mutate, reason, evidence) in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                mutate(repo)
                self.assert_decision_with(repo, base, reason, evidence)

    @staticmethod
    def _case_collision(repo: Path) -> None:
        write(repo / "CollisionProbe.txt", "upper\n")
        write(repo / "collisionprobe.txt", "lower\n")


if __name__ == "__main__":
    unittest.main()
