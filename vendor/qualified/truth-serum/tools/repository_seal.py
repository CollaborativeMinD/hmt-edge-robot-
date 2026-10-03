from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from seal_contract import load, write  # noqa: E402  # pylint: disable=wrong-import-position
from seal_inventory import (  # noqa: E402  # pylint: disable=wrong-import-position
    RUNTIME,
    SEAL,
    inventory,
    preflight,
)


def run_admission(repo: Path) -> None:
    command = [
        sys.executable, "truth_serum.py", "--repo", ".", "--mode", "ci",
        "--out", "evidence/closeout/runtime",
    ]
    result = subprocess.run(command, cwd=repo, check=False)  # nosec B603: fixed argv, no shell.
    if result.returncode != 0:
        raise RuntimeError(f"Truth Serum admission returned {result.returncode}")


def create(repo: Path) -> int:
    issues = preflight(repo)
    if issues:
        raise RuntimeError("; ".join(issues))
    run_admission(repo)
    tree_hash, count, size = inventory(repo)
    payload = {
        "schema_id": "truth_serum.repository_seal",
        "schema_version": "1.0.0",
        "algorithm": "sha256-path-size-content-v1",
        "excluded_paths": [SEAL, RUNTIME],
        "file_count": count,
        "byte_count": size,
        "tree_sha256": tree_hash,
    }
    write(repo / SEAL, payload)
    print(f"PASS {tree_hash} files={count}")
    return 0


def verify(repo: Path) -> int:
    issues = preflight(repo, allow_runtime=True)
    if issues:
        print(f"FAIL {'; '.join(issues)}", file=sys.stderr)
        return 1
    payload = load(repo / SEAL)
    tree_hash, count, size = inventory(repo)
    expected = (payload.get("tree_sha256"), payload.get("file_count"), payload.get("byte_count"))
    actual = (tree_hash, count, size)
    if expected != actual:
        print("FAIL repository seal mismatch", file=sys.stderr)
        return 1
    print(f"PASS {tree_hash} files={count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify the sole repository seal.")
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        return create(repo) if args.action == "create" else verify(repo)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
