"""Strict state extraction for JSON-emitting witnesses."""

from __future__ import annotations

import json
from typing import Any, Literal

NativeState = Literal["CLEAR", "FINDING", "ERROR"]
JSON_TOOLS = {"bandit", "semgrep", "pip-audit"}


def classify(tool: str, raw: str) -> NativeState | None:
    if tool not in JSON_TOOLS:
        return None
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_unique,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError):
        return "ERROR"
    if not isinstance(payload, dict):
        return "ERROR"
    if tool in {"bandit", "semgrep"}:
        return _scanner(payload)
    return _audit(payload)


def _scanner(payload: dict[str, Any]) -> NativeState:
    results = payload.get("results")
    errors = payload.get("errors")
    if not isinstance(results, list) or not isinstance(errors, list):
        return "ERROR"
    if errors:
        return "ERROR"
    return "FINDING" if results else "CLEAR"


def _audit(payload: dict[str, Any]) -> NativeState:
    dependencies = payload.get("dependencies")
    fixes = payload.get("fixes")
    if not isinstance(dependencies, list) or not isinstance(fixes, list):
        return "ERROR"
    vulnerable = False
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(dependency.get("vulns"), list):
            return "ERROR"
        vulnerable = vulnerable or bool(dependency["vulns"])
    return "FINDING" if vulnerable else "CLEAR"


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate native-output key: {key}")
        payload[key] = value
    return payload


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite native-output value: {value}")
