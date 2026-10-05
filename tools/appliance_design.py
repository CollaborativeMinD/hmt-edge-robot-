"""Admit reviewed appliance inputs before building or acquiring release secrets."""
from __future__ import annotations

import json
from pathlib import Path

from ci_admission import ROOT, confined, digest

FILES = {".github/workflows/release.yml", "deploy/appliance/inputs.json", "deploy/appliance/build-image.sh",
    "deploy/appliance/smoke-test.sh", "deploy/appliance/k3s.service", "deploy/appliance/hmt-firstboot.service",
    "deploy/appliance/hmt-runtime.service", "deploy/appliance/k3s-start.sh", "deploy/appliance/runtime-start.sh",
    "deploy/appliance/readiness.py", "deploy/appliance/node.example.json", "tools/appliance_process.py",
    "tools/appliance_node.py", "tools/appliance_firstboot.py", "tools/appliance_workload.py",
    "tools/appliance_prepare.py", "tools/appliance_fetch.py", "tools/appliance_signature.py",
    "tools/appliance_release.py", "tools/appliance_design.py", "tests/test_appliance_node.py",
    "tests/test_appliance_signing.py", "tests/test_appliance_pipeline.py", "tests/test_appliance_release.py", "docs/cd/appliance.md",
    "docs/cd/appliance-requirements.json", "docs/cd/appliance-release-notes.md", "tools/appliance_host.py",
    "deploy/appliance/qualify-host.sh", "tests/test_appliance_host.py"}


def evaluate(root: Path) -> dict:
    catalog = json.loads(confined(root, "policy/appliance_admission.json").read_text())
    if set(catalog) != {"schema_version", "scope", "files"} or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1 or catalog["scope"] != "PI_SIL_SOFTWARE_APPLIANCE":
        raise ValueError("APPLIANCE_CATALOG_SCHEMA")
    if set(catalog["files"]) != FILES:
        raise ValueError("APPLIANCE_CATALOG_INCOMPLETE")
    for name, expected in catalog["files"].items():
        if digest(confined(root, name)) != expected:
            raise ValueError("APPLIANCE_INPUT_DRIFT")
    return {"status": "PASS", "scope": catalog["scope"], "hardware": "HOLD", "native_pi": "NOT_RUN"}


if __name__ == "__main__":
    print(json.dumps(evaluate(ROOT)))
