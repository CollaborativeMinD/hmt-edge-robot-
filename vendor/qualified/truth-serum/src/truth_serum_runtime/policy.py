"""Closed lane-policy loading and mode resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import AdmissionMode
from .witnesses import TOOLS

LOCAL = (
    "architecture-trace",
    "repository-shape",
    "source-aperture",
    "structured-data",
    "evidence-binding",
    "secret-scan",
    "shell-syntax",
)
EXTERNAL = tuple(f"witness-{tool}" for tool in TOOLS)
MODES = {
    "architecture-only": {"required": "local", "external": "NOT_APPLICABLE"},
    "ci": {"required": "all", "external": "REQUIRED"},
    "post-build": {"required": "all", "external": "REQUIRED"},
    "rainy-day": {"required": "all", "external": "REQUIRED"},
}


class PolicyError(ValueError):
    """The submitted lane policy does not match the executable contract."""


def read(path: Path) -> dict[str, Any]:
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise PolicyError(str(error)) from error
    if not isinstance(documents, list) or len(documents) != 1:
        raise PolicyError("lane policy must contain exactly one YAML document")
    payload = documents[0]
    if not isinstance(payload, dict):
        raise PolicyError("lane policy must be an object")
    expected = {
        "schema_id": "truth-serum.lane-policy",
        "schema_version": "1.0.0",
        "aggregation_precedence": ["ESCALATE", "FAIL", "HOLD", "PASS"],
        "status_routes": {
            "PASS": "PASS",
            "NOT_APPLICABLE": "PASS",
            "FAIL": "FAIL",
            "UNAVAILABLE": "HOLD",
            "ERROR": "HOLD",
        },
        "local_lanes": list(LOCAL),
        "external_lanes": list(EXTERNAL),
        "modes": MODES,
        "rules": {
            "unavailable_required_witness": "HOLD",
            "witness_execution_error": "HOLD",
            "blocking_finding": "FAIL",
            "terminal_finding": "ESCALATE",
            "absent_target": "NOT_APPLICABLE",
        },
    }
    if payload != expected:
        raise PolicyError("lane policy differs from the executable 1.0.0 contract")
    return payload


def requires_external(path: Path, mode: AdmissionMode) -> bool:
    payload = read(path)
    return bool(payload["modes"][mode.value]["external"] == "REQUIRED")
