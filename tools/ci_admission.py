"""Standard-library admission preflight; never executes candidate archives."""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = Path("policy/ci_admission.json")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confined(root: Path, name: str) -> Path:
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("PATH_OUTSIDE_ADMISSION_ROOT")
    if any(part.is_symlink() for part in [path, *path.parents] if part != root.parent):
        raise ValueError("SYMLINK_NOT_ADMITTED")
    if not path.is_file() or path.resolve().is_relative_to(root.resolve()) is False:
        raise ValueError("ADMISSION_FILE_UNAVAILABLE")
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("ADMISSION_FILE_TOO_LARGE")
    return path


def exact_fields(value: dict[str, Any], names: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("ADMISSION_SCHEMA_MISMATCH")


def evaluate(root: Path) -> dict[str, Any]:
    policy = json.loads(confined(root, str(POLICY)).read_text())
    exact_fields(policy, {"schema_version", "target", "files", "tools", "candidates"})
    if type(policy["schema_version"]) is not int or policy["schema_version"] != 1:
        raise ValueError("ADMISSION_SCHEMA_VERSION")
    if policy["target"] != {"os": "linux", "architecture": "aarch64", "orchestrator": "k3s", "deployment": "HOLD"}:
        raise ValueError("DEPLOYMENT_TARGET_MISMATCH")
    if not isinstance(policy["files"], dict) or not 1 <= len(policy["files"]) <= 32:
        raise ValueError("ADMISSION_FILE_COUNT")
    for name, expected in policy["files"].items():
        if digest(confined(root, name)) != expected:
            raise ValueError("ADMISSION_DIGEST_MISMATCH:" + name)
    lock = tomllib.loads(confined(root, "uv.lock").read_text())
    packages = {entry["name"]: entry["version"] for entry in lock["package"]}
    if set(policy["tools"]) != {"pyrefly", "ruff", "pytest", "pytest-cov", "marimo"}:
        raise ValueError("TOOL_ALLOWLIST_MISMATCH")
    for name, version in policy["tools"].items():
        if packages.get(name) != version:
            raise ValueError("TOOL_VERSION_NOT_ADMITTED:" + name)
    candidates = policy["candidates"]
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise ValueError("CANDIDATE_COUNT")
    for candidate in candidates:
        exact_fields(candidate, {"name", "path", "sha256", "status", "reason"})
        if candidate["status"] != "HOLD" or not candidate["reason"]:
            raise ValueError("CANDIDATE_EXECUTION_NOT_ADMITTED")
        if digest(confined(root, candidate["path"])) != candidate["sha256"]:
            raise ValueError("CANDIDATE_DIGEST_MISMATCH")
    return {"status": "PASS", "reason_codes": ["CI_TOOLCHAIN_ADMITTED"],
            "policy_sha256": digest(root / POLICY), "lock_sha256": digest(root / "uv.lock"),
            "target": policy["target"], "tools": policy["tools"], "candidates": candidates}


def main(root: Path = ROOT) -> int:
    result: dict[str, Any]
    try:
        result = evaluate(root)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {"status": "FAIL", "reason_codes": [str(exc)]}
    result["notification"] = "CI_ADMISSION_" + result["status"]
    result["alert"] = result["status"] != "PASS"
    destination = root / "evidence/ci/admission.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps(result))
    if result["alert"]:
        print("::error::CI admission failed; inspect evidence/ci/admission.json")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
