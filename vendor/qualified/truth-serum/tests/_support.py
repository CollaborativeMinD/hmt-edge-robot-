from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALID_MODES = ("architecture-only", "ci", "post-build", "rainy-day")
MANDATORY_TOOLS = (
    "ruff",
    "pylint",
    "mypy",
    "bandit",
    "semgrep",
    "yamllint",
    "pytest",
    "pip-audit",
)
REPORT_FIELDS = {
    "schema_id",
    "schema_version",
    "attempt_id",
    "mode",
    "decision",
    "posture",
    "clear",
    "reasons",
    "lanes",
    "evidence_dir",
    "policy_path",
}
OUT = Path("evidence/runtime")


def copy_release(destination: Path) -> Path:
    repo = destination / "repo"

    def ignored(_directory: str, names: list[str]) -> set[str]:
        ignored_names = {
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
        }
        ignored_names.update(name for name in names if name == "REPOSITORY_SEAL.json")
        return ignored_names

    shutil.copytree(ROOT, repo, ignore=ignored)
    shutil.rmtree(repo / "evidence", ignore_errors=True)
    return repo


def run_admission(
    repo: Path,
    mode: str,
    *,
    out: Path = OUT,
    path: str | None = None,
    attempt_id: str = "acceptance-attempt",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    if path is not None:
        environment["PATH"] = path
    command = [
        sys.executable,
        "truth_serum.py",
        "--repo",
        ".",
        "--mode",
        mode,
        "--out",
        out.as_posix(),
        "--attempt-id",
        attempt_id,
    ]
    return subprocess.run(
        command,
        cwd=repo,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def report(repo: Path, out: Path = OUT) -> dict[str, Any]:
    return strict_json(repo / out / "admission_report.json")


def strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")

    parsed = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate,
        parse_constant=reject_constant,
    )
    if not isinstance(parsed, dict):
        raise TypeError(f"expected object in {path}")
    return parsed


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stubbed_path(directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    for tool in MANDATORY_TOOLS:
        target = directory / tool
        if tool in {"bandit", "semgrep"}:
            body = "#!/bin/sh\nprintf '%s\\n' '{\"results\":[],\"errors\":[]}'\nexit 0\n"
        elif tool == "pip-audit":
            body = "#!/bin/sh\nprintf '%s\\n' '{\"dependencies\":[],\"fixes\":[]}'\nexit 0\n"
        else:
            body = "#!/bin/sh\nexit 0\n"
        write(target, body)
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
    return os.pathsep.join((str(directory), os.environ.get("PATH", "")))


def tree_digest(repo: Path, excluded: Path = OUT) -> dict[str, str]:
    state: dict[str, str] = {}
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(repo)
        if relative == excluded or excluded in relative.parents:
            continue
        state[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


def report_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def seal_command(repo: Path, action: str, path: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PATH"] = path
    return subprocess.run(
        [sys.executable, "tools/repository_seal.py", action, "--repo", "."],
        cwd=repo,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
