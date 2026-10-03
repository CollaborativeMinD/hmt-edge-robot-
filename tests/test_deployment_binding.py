"""Reject incomplete, stale, escaped and substituted release inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ci_admission import ROOT
from deployment_admission import evaluate
from deployment_support import deployment_copy, mutate, rewrite


@pytest.mark.parametrize("mutation", ["tamper", "missing", "link", "source", "new_source", "extra_manifest"])
def test_release_binding_denies_input_drift(tmp_path: Path, mutation: str) -> None:
    root = deployment_copy(tmp_path)
    path = root / "policy/deployment.json"
    if mutation == "tamper":
        path.write_text("{}")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "link":
        path.unlink()
        path.symlink_to(ROOT / "policy/deployment.json")
    elif mutation == "source":
        (root / "src/hmt_edge_robot/cli.py").write_text("# substituted source\n")
    elif mutation == "new_source":
        (root / "src/unreviewed.py").write_text("value = 1\n")
    else:
        (root / "deploy/stage3/extra.json").write_text("{}")
    with pytest.raises(ValueError):
        evaluate(root)


@pytest.mark.parametrize("mutation", ["omission", "escape", "object", "capacity"])
def test_catalog_requires_complete_confined_bindings(tmp_path: Path, mutation: str) -> None:
    root = deployment_copy(tmp_path)
    path = root / "policy/deployment_admission.json"
    catalog = json.loads(path.read_text())
    if mutation == "omission":
        catalog["inputs"].pop("uv.lock")
    elif mutation == "escape":
        catalog["inputs"]["../escape.json"] = "a" * 64
    elif mutation == "capacity":
        catalog["inputs"].update({"unreviewed-" + str(i): "a" * 64 for i in range(33)})
    else:
        catalog["inputs"] = []
    rewrite(root, "policy/deployment_admission.json", catalog)
    with pytest.raises(ValueError):
        evaluate(root)


@pytest.mark.parametrize("name,keys,value,code", [
    ("policy/deployment.json", ("baseline", "commit"), "a" * 40, "BASELINE_MISMATCH"),
    ("policy/release_candidate.json", ("baseline", "tree"), "a" * 40, "BASELINE_MISMATCH"),
    ("policy/release_candidate.json", ("plan_sha256",), "a" * 64, "PLAN_MISMATCH"),
    ("policy/release_candidate.json", ("source_inventory_sha256",), "a" * 64, "SOURCE_BINDING_MISMATCH"),
    ("policy/deployment_runtime.json", ("allow_cloud",), True, "CLOUD_NOT_AUTHORIZED"),
])
def test_release_rejects_stale_baseline_policy_and_cloud(tmp_path: Path, name: str, keys: tuple[str | int, ...], value: object, code: str) -> None:
    root = deployment_copy(tmp_path)
    mutate(root, name, keys, value)
    with pytest.raises(ValueError, match=code):
        evaluate(root)
