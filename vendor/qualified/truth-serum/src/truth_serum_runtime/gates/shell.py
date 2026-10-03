"""Shell syntax and strict-mode checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..files import relative, repository_files
from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus


def run(root: Path, out: Path) -> LaneReport:
    paths = [path for path in repository_files(root, out) if path.suffix == ".sh"]
    if not paths:
        return lane("shell-syntax", LaneStatus.NOT_APPLICABLE, "bash", ("NOT_APPLICABLE_SHELL",))
    if shutil.which("bash") is None:
        return lane("shell-syntax", LaneStatus.UNAVAILABLE, "bash", ("HOLD_BASH_UNAVAILABLE",))
    findings = tuple(item for path in paths for item in _inspect(path, root))
    if findings:
        return lane(
            "shell-syntax",
            LaneStatus.FAIL,
            "bash",
            tuple(x.reason_code for x in findings),
            findings,
        )
    return lane("shell-syntax", LaneStatus.PASS, "bash", ("PASS_SHELL_SYNTAX",))


def _inspect(path: Path, root: Path) -> list[Finding]:
    rel = relative(path, root)
    findings: list[Finding] = []
    content = path.read_text(encoding="utf-8")
    commands = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "#!"))
    ]
    if not commands or commands[0] != "set -euo pipefail":
        findings.append(
            Finding(
                reason_code="FAIL_SHELL_STRICT_MODE",
                message="Shell script lacks set -euo pipefail.",
                path=rel,
            )
        )
    # Fixed bash syntax-only invocation; no shell expansion is used.
    result = subprocess.run(  # nosec B603, B607
        ["bash", "-n", str(path)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip().splitlines()[0]
        findings.append(Finding(reason_code="FAIL_SHELL_SYNTAX", message=message, path=rel))
    return findings
