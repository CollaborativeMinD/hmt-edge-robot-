from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import copy_release, seal_command, stubbed_path, write

SEAL = "REPOSITORY_SEAL.json"
LEDGER_TOKENS = ("checksum", "hash_ledger", "manifest.sha256")


class SealAndHygieneTests(unittest.TestCase):
    def test_sole_seal_create_verify_and_governed_byte_tamper_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            path = stubbed_path(base / "bin")
            created = seal_command(repo, "create", path)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue((repo / SEAL).is_file())
            seal_artifacts = [
                item.relative_to(repo).as_posix() for item in repo.rglob("*SEAL*.json")
            ]
            self.assertEqual(seal_artifacts, [SEAL])
            extra_ledgers = [
                item.relative_to(repo).as_posix()
                for item in repo.rglob("*")
                if item.is_file()
                and item.name != SEAL
                and any(token in item.name.lower() for token in LEDGER_TOKENS)
            ]
            self.assertEqual(extra_ledgers, [])
            verified = seal_command(repo, "verify", path)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            target = repo / "README.md"
            target.write_bytes(target.read_bytes() + b"X")
            rejected = seal_command(repo, "verify", path)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("repository seal mismatch", rejected.stderr)

    def test_seal_rejects_one_byte_tamper_of_retained_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repo = copy_release(base)
            path = stubbed_path(base / "bin")
            created = seal_command(repo, "create", path)
            self.assertEqual(created.returncode, 0, created.stderr)
            raw = sorted((repo / "evidence/closeout/runtime/raw").glob("*.txt"))
            self.assertGreaterEqual(len(raw), 1)
            raw[0].write_bytes(raw[0].read_bytes() + b"\x00")
            rejected = seal_command(repo, "verify", path)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("repository seal mismatch", rejected.stderr)

    def test_seal_preflight_rejects_extra_ledgers_debris_and_case_collisions(self) -> None:
        mutations = {
            "extra-ledger": lambda repo: write(repo / "rogue_hash_ledger.csv", "path,sha256\n"),
            "build-debris": lambda repo: write(repo / "build/sentinel.txt", "must block\n"),
            "dist-debris": lambda repo: write(repo / "dist/sentinel.txt", "must block\n"),
            "runtime-debris": lambda repo: write(
                repo / "evidence/runtime/sentinel.txt", "must block\n"
            ),
            "cache-debris": lambda repo: write(repo / ".venv/sentinel.txt", "must block\n"),
            "case-collision": self._case_collision,
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                mutate(repo)
                result = seal_command(repo, "create", stubbed_path(base / "bin"))
                self.assertEqual(result.returncode, 1)
                self.assertFalse((repo / SEAL).exists())

    def test_verify_rejects_post_seal_cache_and_envelope_tampering(self) -> None:
        for name in ("cache", "algorithm"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                path = stubbed_path(base / "bin")
                created = seal_command(repo, "create", path)
                self.assertEqual(created.returncode, 0, created.stderr)
                if name == "cache":
                    write(repo / ".pytest_cache/sentinel.txt", "post-seal debris\n")
                else:
                    seal = repo / SEAL
                    seal.write_text(
                        seal.read_text(encoding="utf-8").replace(
                            "sha256-path-size-content-v1", "tampered"
                        ),
                        encoding="utf-8",
                    )
                rejected = seal_command(repo, "verify", path)
                self.assertEqual(rejected.returncode, 1)

    def test_verify_rejects_symlinks_inside_ephemeral_runtime(self) -> None:
        for name in ("runtime-root", "runtime-nested"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                repo = copy_release(base)
                path = stubbed_path(base / "bin")
                created = seal_command(repo, "create", path)
                self.assertEqual(created.returncode, 0, created.stderr)
                outside = base / "outside"
                outside.mkdir()
                runtime = repo / "evidence/runtime"
                if name == "runtime-root":
                    runtime.symlink_to(outside, target_is_directory=True)
                else:
                    runtime.mkdir(parents=True)
                    (runtime / "escape").symlink_to(outside, target_is_directory=True)
                rejected = seal_command(repo, "verify", path)
                self.assertEqual(rejected.returncode, 1)

    @staticmethod
    def _case_collision(repo: Path) -> None:
        write(repo / "CaseProbe.txt", "upper\n")
        write(repo / "caseprobe.txt", "lower\n")


if __name__ == "__main__":
    unittest.main()
