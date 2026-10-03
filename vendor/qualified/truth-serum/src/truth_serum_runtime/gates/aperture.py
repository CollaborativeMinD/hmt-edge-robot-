"""Python syntax and source-aperture enforcement."""

from __future__ import annotations

import ast
from pathlib import Path

from ..files import relative
from ..lanes import lane
from ..models import Finding, LaneReport, LaneStatus


def run(root: Path, _out: Path) -> LaneReport:
    paths = sorted((root / "src").rglob("*.py"))
    paths.extend(sorted((root / "tools").rglob("*.py")))
    if (root / "truth_serum.py").is_file():
        paths.append(root / "truth_serum.py")
    if not paths:
        return lane(
            "source-aperture", LaneStatus.NOT_APPLICABLE, "ast", ("NOT_APPLICABLE_SOURCE_APERTURE",)
        )
    findings = tuple(item for path in paths for item in _inspect(path, root))
    if findings:
        return lane(
            "source-aperture",
            LaneStatus.FAIL,
            "ast",
            tuple(x.reason_code for x in findings),
            findings,
        )
    return lane("source-aperture", LaneStatus.PASS, "ast", ("PASS_SOURCE_APERTURE",))


def _inspect(path: Path, root: Path) -> list[Finding]:
    rel = relative(path, root)
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: list[Finding] = []
    if len(lines) >= 100:
        findings.append(
            Finding(
                reason_code="FAIL_SOURCE_MODULE_APERTURE",
                message=f"Module has {len(lines)} physical lines; limit is 99.",
                path=rel,
            )
        )
    try:
        tree = ast.parse("\n".join(lines), filename=rel)
    except SyntaxError as error:
        return [
            Finding(
                reason_code="FAIL_SOURCE_SYNTAX", message=error.msg, path=rel, line=error.lineno
            )
        ]
    nodes = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in (item for item in ast.walk(tree) if isinstance(item, nodes)):
        end = node.end_lineno or node.lineno
        length = end - node.lineno + 1
        if length > 60:
            findings.append(
                Finding(
                    reason_code="FAIL_SOURCE_FUNCTION_APERTURE",
                    message=f"Function {node.name} has {length} lines; limit is 60.",
                    path=rel,
                    line=node.lineno,
                )
            )
    return findings
