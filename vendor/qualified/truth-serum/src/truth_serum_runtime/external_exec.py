"""External witness process and raw-output mechanics."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .files import write_text
from .witnesses import command


def invoke(tool: str, root: Path, out: Path) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix=f"truth-serum-{tool}-") as directory:
        state = Path(directory)
        env = dict(os.environ)
        env["MYPY_CACHE_DIR"] = str(state / "mypy")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["RUFF_CACHE_DIR"] = str(state / "ruff")
        env["SEMGREP_LOG_FILE"] = str(state / "semgrep.log")
        env["SEMGREP_SETTINGS_FILE"] = str(state / "settings.yml")
        env["SEMGREP_VERSION_CACHE_PATH"] = str(state / "version-cache")
        env["XDG_CACHE_HOME"] = str(state / "cache")
        env["XDG_CONFIG_HOME"] = str(state / "config")
        # Commands are closed argv contracts; no shell expansion is used.
        return subprocess.run(  # nosec B603
            command(tool, root, out),
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=180,
            check=False,
        )


def write_raw(tool: str, out: Path, stdout: str, stderr: str) -> tuple[str, ...]:
    stdout_ref = f"raw/{tool}.stdout.txt"
    stderr_ref = f"raw/{tool}.stderr.txt"
    write_text(out / stdout_ref, stdout)
    write_text(out / stderr_ref, stderr)
    return (stderr_ref, stdout_ref)


def execution_error(tool: str, code: int) -> bool:
    if code == 0:
        return False
    if tool == "pylint":
        return bool(code & 33)
    finding_codes = {"ruff": 1, "mypy": 1, "bandit": 1, "semgrep": 1, "yamllint": 1}
    if tool in finding_codes:
        return code != finding_codes[tool]
    return tool in {"pytest", "pip-audit"} and code != 1
