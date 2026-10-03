"""High-confidence local secret exposure scan."""

from __future__ import annotations

import re
from pathlib import Path

from ..files import relative, repository_files, text
from ..lanes import lane
from ..models import Decision, Finding, LaneReport, LaneStatus

PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"(?i)(?:^|[^A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*"
        r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?"
        r"[A-Za-z0-9+/=_-]{20,}['\"]?"
    ),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
)
SECRET_PATHS = {".secrets", "secrets"}


def run(root: Path, out: Path) -> LaneReport:
    scanned = 0
    findings: list[Finding] = []
    for path in repository_files(root, out):
        rel = relative(path, root)
        if _secret_path(path, root):
            findings.append(
                Finding(
                    reason_code="ESCALATE_SECRET_EXPOSURE",
                    message="Prohibited secret-bearing path is present.",
                    path=rel,
                    route=Decision.ESCALATE,
                )
            )
        content = text(path)
        if content is None:
            continue
        scanned += 1
        for number, line_text in enumerate(content.splitlines(), start=1):
            if any(pattern.search(line_text) for pattern in PATTERNS):
                findings.append(
                    Finding(
                        reason_code="ESCALATE_SECRET_EXPOSURE",
                        message="High-confidence secret material detected.",
                        path=rel,
                        line=number,
                        route=Decision.ESCALATE,
                    )
                )
    if findings:
        return lane(
            "secret-scan", LaneStatus.FAIL, "local", ("ESCALATE_SECRET_EXPOSURE",), tuple(findings)
        )
    if scanned == 0:
        return lane(
            "secret-scan", LaneStatus.NOT_APPLICABLE, "local", ("NOT_APPLICABLE_SECRET_SCAN",)
        )
    return lane("secret-scan", LaneStatus.PASS, "local", ("PASS_SECRET_SCAN",))


def _secret_path(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part in SECRET_PATHS or part.startswith(".env") for part in parts)
