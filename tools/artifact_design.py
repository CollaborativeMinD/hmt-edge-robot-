"""Read-only admission of stage-4 build inputs; runtime proof occurs in Actions."""
from __future__ import annotations

import json
from pathlib import Path

from ci_admission import ROOT, confined, digest


def evaluate(root: Path) -> dict:
    catalog = json.loads(confined(root, "policy/artifact_admission.json").read_text())
    if not isinstance(catalog, dict) or set(catalog) != {"schema_version", "scope", "files"} or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1:
        raise ValueError("ARTIFACT_CATALOG_SCHEMA_MISMATCH")
    if catalog["scope"] != "ARM64_ARTIFACT_QUALIFICATION_ONLY":
        raise ValueError("ARTIFACT_AUTHORITY_WIDENED")
    if not isinstance(catalog["files"], dict) or not 1 <= len(catalog["files"]) <= 32:
        raise ValueError("ARTIFACT_CATALOG_BOUNDS")
    for name, expected in catalog["files"].items():
        if digest(confined(root, name)) != expected:
            raise ValueError("ARTIFACT_INPUT_DRIFT")
    return {"status": "PASS", "scope": catalog["scope"], "deployment": "HOLD",
            "hardware": "HOLD", "artifact_runtime_qualification": "PENDING_ACTIONS",
            "catalog_sha256": digest(root / "policy/artifact_admission.json")}


if __name__ == "__main__":
    print(json.dumps(evaluate(ROOT)))
