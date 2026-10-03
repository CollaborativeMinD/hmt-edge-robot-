"""Receipts remain design-only, replayable, source-bound and fail closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from deployment_admission import evaluate
from deployment_contracts import DeploymentPlan
from deployment_gate import main
from deployment_receipts import require_execution, verify_receipt
from deployment_support import deployment_copy, mutate, rewrite
from deployment_workload import workload


def test_design_receipt_replay_preserves_every_execution_hold(tmp_path: Path) -> None:
    root = deployment_copy(tmp_path)
    first = evaluate(root)
    assert first == evaluate(root)
    assert verify_receipt(first, first.model_dump_json().encode()) == first
    assert first.contract_status == "PASS" and first.release_decision == "HOLD"
    assert first.image_digest is None and first.authority == "DESIGN_ONLY"
    assert set(first.boundaries.model_dump().values()) == {"HOLD"}
    with pytest.raises(PermissionError, match="EXECUTION_NOT_AUTHORIZED"):
        require_execution(first)
    assert main(root) == 0
    raw = (root / "evidence/cd/stage3/release_receipt.json").read_bytes()
    assert verify_receipt(first, raw) == first


@pytest.mark.parametrize("mutation", ["hash", "authority", "unknown", "oversize", "duplicate", "stale"])
def test_receipt_forgery_and_stale_inputs_are_denied(tmp_path: Path, mutation: str) -> None:
    root = deployment_copy(tmp_path)
    first = evaluate(root)
    value = first.model_dump(mode="json")
    expected = first
    if mutation == "hash":
        value["receipt_hash"] = "a" * 64
    elif mutation == "authority":
        value["release_decision"] = "ADMIT"
    elif mutation == "unknown":
        value["cluster_credentials"] = "unreviewed"
    elif mutation == "stale":
        mutate(root, "policy/deployment.json", ("resources", "request_cpu_m"), 600)
        candidate = json.loads((root / "policy/release_candidate.json").read_text())
        import hashlib
        candidate["plan_sha256"] = hashlib.sha256((root / "policy/deployment.json").read_bytes()).hexdigest()
        rewrite(root, "policy/release_candidate.json", candidate, repin=True)
        plan = DeploymentPlan.model_validate(json.loads((root / "policy/deployment.json").read_text()))
        rewrite(root, "deploy/stage3/workload/workload.template.json", workload(plan), repin=True)
        expected = evaluate(root)
    raw = json.dumps(value).encode()
    if mutation == "oversize":
        raw = b" " * 65537
    elif mutation == "duplicate":
        raw = raw[:-1] + b', "release_decision": "HOLD"}'
    with pytest.raises(ValueError):
        verify_receipt(expected, raw)


def test_evidence_failure_blocks_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = deployment_copy(tmp_path)
    def failed_replace(path: Path, target: Path) -> None:
        raise OSError("injected evidence persistence failure")
    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="persistence failure"):
        main(root)
