from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

OUTPUT = "evidence/artifact_manifest.json"
EXCLUDE_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
MODIFIED_PREFIXES = ("architecture/", "contracts/", "src/", "tests/", "uv.lock")


def paths(repo: Path) -> list[str]:
    found: list[str] = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDE_DIRS)
        for name in sorted(names):
            relative = (Path(root) / name).relative_to(repo).as_posix()
            if relative not in {OUTPUT, "REPOSITORY_SEAL.json"}:
                found.append(relative)
    return [*sorted(found), OUTPUT, "REPOSITORY_SEAL.json"]


def disposition(path: str) -> str:
    return "modified" if path.startswith(MODIFIED_PREFIXES) else "new"


def build(repo: Path) -> dict[str, object]:
    artifacts = [
        {"path": path, "disposition": disposition(path), "reason": "mission-assurance-rebuild"}
        for path in paths(repo)
    ]
    return {
        "schema_id": "truth_serum.artifact_manifest",
        "schema_version": "1.0.0",
        "provenance_id": "prov_truth_serum_blue_closeout_v1_0_0",
        "artifacts": artifacts,
        "blocked_inputs": [
            "candidate:contradictory-evidence-trees",
            "candidate:stale-checksum-ledgers",
            "candidate:fail-open-deployment-probes",
            "candidate:unbounded-production-modules",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the non-hash closeout artifact manifest.")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    target = repo / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build(repo), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
