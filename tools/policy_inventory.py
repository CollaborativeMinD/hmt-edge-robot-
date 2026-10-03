"""Measure declared policy gaps without silently promoting candidate policies."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path
from typing import Any

from ci_admission import confined, digest
from policy_contracts import SupportProfile
from truth_serum_runtime.gates.data_parse import loads_json


def load_profile(root: Path) -> SupportProfile:
    return SupportProfile.model_validate_json(confined(root, "policy/ci_support.json").read_bytes())


def inventory(root: Path, profile: SupportProfile) -> list[dict[str, Any]]:
    result = []
    for name, expected in profile.policy_sources.items():
        path = confined(root, name)
        if digest(path) != expected:
            raise ValueError("DECLARATIVE_POLICY_DIGEST_MISMATCH:" + name)
        if path.suffix == ".json":
            value = loads_json(path.read_text())
            if not isinstance(value, dict):
                raise ValueError("POLICY_OBJECT_REQUIRED")
            result.append({"path": name, "sha256": expected,
                           "policy_id": value.get("policy_id", value.get("baseline_id", "DATA")),
                           "declared_status": value.get("status", "UNSPECIFIED"),
                           "adoption": "EVALUATED_NOT_GLOBALLY_PROMOTED"})
    return result


def fold_measurements(root: Path) -> list[dict[str, Any]]:
    files = sorted(p for d in ("src", "tests", "tools", "notebooks")
                   for p in (root / d).rglob("*.py") if "__pycache__" not in p.parts)
    if len(files) > 256:
        raise ValueError("SOURCE_INVENTORY_CAPACITY")
    result = []
    for path in files:
        text = confined(root, path.relative_to(root).as_posix()).read_text()
        lines = text.splitlines()
        comments = {token.start[0] for token in tokenize.generate_tokens(io.StringIO(text).readline)
                    if token.type == tokenize.COMMENT and not lines[token.start[0]-1][:token.start[1]].strip()}
        count = sum(bool(line.strip()) and index not in comments
                    for index, line in enumerate(lines, start=1))
        tree = ast.parse(text)
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        longest = max(((node.end_lineno or node.lineno) - node.lineno + 1
                       for node in functions), default=0)
        result.append({"path": path.relative_to(root).as_posix(), "module_loc": count,
                       "max_function_physical_loc": longest,
                       "module_status": "HOLD" if count > 100 else "PASS",
                       "function_status": "FAIL" if longest > 60 else "PASS"})
    return result
