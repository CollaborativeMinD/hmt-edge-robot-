from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from seal_inventory import RUNTIME, SEAL

FIELDS = {
    "schema_id",
    "schema_version",
    "algorithm",
    "excluded_paths",
    "file_count",
    "byte_count",
    "tree_sha256",
}
IDENTITY = {
    "schema_id": "truth_serum.repository_seal",
    "schema_version": "1.0.0",
    "algorithm": "sha256-path-size-content-v1",
    "excluded_paths": [SEAL, RUNTIME],
}


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique,
        parse_constant=_reject_constant,
    )
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError("repository seal fields do not match the closed contract")
    if any(payload.get(key) != value for key, value in IDENTITY.items()):
        raise ValueError("repository seal identity does not match the closed contract")
    if re.fullmatch(r"[0-9a-f]{64}", payload.get("tree_sha256", "")) is None:
        raise ValueError("repository seal digest is malformed")
    for key in ("file_count", "byte_count"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"repository seal {key} is malformed")
    return payload


def write(path: Path, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(rendered)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate repository seal key: {key}")
        payload[key] = value
    return payload


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite repository seal value: {value}")
