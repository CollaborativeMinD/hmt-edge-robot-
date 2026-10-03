"""Evaluate historical source-pin availability without substituting guessed evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ci_admission import digest
from truth_serum_runtime.gates.data_parse import loads_json


def source_pins(root: Path, paths: dict[str, str]) -> list[dict[str, Any]]:
    by_name: dict[str, list[Path]] = {}
    for name in paths:
        path = root / name
        by_name.setdefault(path.name, []).append(path)
    result = []
    for name in paths:
        path = root / name
        if path.suffix != ".json":
            continue
        value = loads_json(path.read_text())
        pending = [value]
        visited = 0
        while pending:
            node = pending.pop()
            visited += 1
            if visited > 8192:
                raise ValueError("POLICY_NODE_CAPACITY")
            if isinstance(node, dict):
                if "artifact" in node and "sha256" in node:
                    matches = by_name.get(str(node["artifact"]), [])
                    exact = any(digest(candidate) == node["sha256"] for candidate in matches)
                    status = "PASS" if exact else "MISMATCH" if matches else "UNAVAILABLE"
                    result.append({"policy": name, "artifact": node["artifact"],
                                   "expected_sha256": node["sha256"], "status": status})
                pending.extend(node.values())
            elif isinstance(node, list):
                pending.extend(node)
    return result
