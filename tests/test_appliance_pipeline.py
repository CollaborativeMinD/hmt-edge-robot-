"""Release integrity and credential isolation remain independently testable in PR CI."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from appliance_design import FILES, evaluate

ROOT = Path(__file__).resolve().parents[1]


def test_appliance_catalog_requires_every_reviewed_input(tmp_path: Path) -> None:
    for name in {*FILES, "policy/appliance_admission.json"}:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    assert evaluate(tmp_path)["hardware"] == "HOLD"
    (tmp_path / "deploy/appliance/inputs.json").write_text("changed")
    with pytest.raises(ValueError, match="DRIFT"):
        evaluate(tmp_path)
    path = tmp_path / "policy/appliance_admission.json"
    catalog = json.loads(path.read_text())
    catalog["files"].pop("deploy/appliance/inputs.json")
    path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="INCOMPLETE"):
        evaluate(tmp_path)


def test_release_secrets_only_enter_the_protected_publisher() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text()
    assert "pull_request:" not in workflow
    jobs = dict(re.findall(r"^  (\w+):\n(.*?)(?=^  \w+:|\Z)", workflow.split("jobs:\n", 1)[1], re.M | re.S))
    publisher = jobs["publish"]
    assert "environment: appliance-release" in publisher and "needs: assemble" in publisher
    assert "contents: write" in publisher and "packages: write" in publisher
    for name, job in jobs.items():
        if name != "publish":
            assert "secrets." not in job
    assert "compare/" in jobs["source"] and "refs/heads/main" in jobs["source"]
    artifact = (ROOT / ".github/workflows/artifact.yml").read_text()
    assert "secrets." not in artifact and "workflow_call:" in artifact
    assert "defaults:\n  run:\n    shell: bash" in artifact
