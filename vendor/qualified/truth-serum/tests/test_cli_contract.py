from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import (
    OUT,
    VALID_MODES,
    copy_release,
    report,
    report_text,
    run_admission,
    stubbed_path,
    tree_digest,
    write,
)


class CommandContractTests(unittest.TestCase):
    def test_all_declared_modes_pass_with_available_witnesses(self) -> None:
        for mode in VALID_MODES:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                path = stubbed_path(base / "bin")
                result = run_admission(repo, mode, path=path)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = report(repo)
                self.assertEqual(payload["mode"], mode)
                self.assertEqual(payload["decision"], "PASS")
                self.assertTrue(payload["clear"])

    def test_invalid_mode_is_contract_error_without_output_or_repo_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            before = tree_digest(repo)
            result = run_admission(repo, "definitely-not-a-mode")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((repo / OUT).exists())
            self.assertEqual(tree_digest(repo), before)

    def test_output_authority_rejects_governed_and_symlink_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            before = tree_digest(repo)
            governed = run_admission(repo, "architecture-only", out=Path("src"))
            self.assertEqual(governed.returncode, 2, governed.stderr)
            self.assertEqual(tree_digest(repo), before)
            target = repo / "evidence/target"
            target.mkdir(parents=True)
            (target / "sentinel.txt").write_text("preserve\n", encoding="utf-8")
            (repo / OUT).symlink_to(target, target_is_directory=True)
            linked = run_admission(repo, "architecture-only")
            self.assertEqual(linked.returncode, 2, linked.stderr)
            self.assertEqual((target / "sentinel.txt").read_text(encoding="utf-8"), "preserve\n")

    def test_reused_output_is_replaced_without_stale_witness_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            path = stubbed_path(base / "bin")
            first = run_admission(repo, "ci", path=path)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((repo / OUT / "raw/ruff.stdout.txt").is_file())
            second = run_admission(repo, "architecture-only", path=path)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse((repo / OUT / "raw").exists())

    def test_unavailable_required_witness_is_hold_exit_three(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            empty_path = base / "empty-path"
            empty_path.mkdir()
            result = run_admission(repo, "ci", path=str(empty_path))
            self.assertEqual(result.returncode, 3, result.stderr)
            payload = report(repo)
            self.assertEqual(payload["decision"], "HOLD")
            self.assertFalse(payload["clear"])
            rendered = report_text(payload)
            self.assertIn("HOLD_WITNESS_RUFF_UNAVAILABLE", rendered)
            self.assertIn('"status": "UNAVAILABLE"', rendered)

    def test_debris_survives_and_blocks_without_other_repository_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            build_marker = repo / "build/sentinel.bin"
            dist_marker = repo / "dist/sentinel.bin"
            build_bytes = b"build-must-survive\x00\xff"
            dist_bytes = b"dist-must-survive\x00\xfe"
            build_marker.parent.mkdir()
            dist_marker.parent.mkdir()
            build_marker.write_bytes(build_bytes)
            dist_marker.write_bytes(dist_bytes)
            before = tree_digest(repo)
            result = run_admission(repo, "architecture-only", path=stubbed_path(base / "bin"))
            self.assertEqual(result.returncode, 1, result.stderr)
            payload = report(repo)
            self.assertEqual(payload["decision"], "FAIL")
            self.assertIn("FAIL_REPOSITORY_SHAPE", report_text(payload))
            self.assertIn("build", report_text(payload))
            self.assertIn("dist", report_text(payload))
            self.assertEqual(build_marker.read_bytes(), build_bytes)
            self.assertEqual(dist_marker.read_bytes(), dist_bytes)
            self.assertEqual(tree_digest(repo), before)

    def test_json_witness_findings_and_malformed_output_fail_closed(self) -> None:
        cases = {
            "semgrep-finding": (
                "semgrep",
                "#!/bin/sh\nprintf '%s\\n' "
                "'{\"results\":[{\"check_id\":\"probe\"}],\"errors\":[]}'\nexit 0\n",
                1,
                "FAIL_WITNESS_SEMGREP_FINDING",
            ),
            "pip-audit-malformed": (
                "pip-audit",
                "#!/bin/sh\nexit 0\n",
                3,
                "HOLD_WITNESS_PIP_AUDIT_ERROR",
            ),
        }
        for name, (tool, body, exit_code, reason) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                bin_dir = base / "bin"
                path = stubbed_path(bin_dir)
                write(bin_dir / tool, body)
                (bin_dir / tool).chmod(0o700)
                result = run_admission(repo, "ci", path=path)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                payload = report(repo)
                self.assertIn(reason, report_text(payload))
                if exit_code == 3:
                    finding = next(
                        item
                        for lane in payload["lanes"]
                        for item in lane["findings"]
                        if item["reason_code"] == reason
                    )
                    self.assertEqual(finding["route"], "HOLD")


if __name__ == "__main__":
    unittest.main()
