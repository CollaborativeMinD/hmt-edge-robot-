"""Human promotion is source-bound and cannot widen deployment authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from policy_evaluation import evaluate, main
from policy_inventory import fold_measurements, load_profile
from policy_promotion import disposition_pins, load_promotion
from test_ci_support import support_copy


def test_promoted_policy_replay_and_historical_disposition(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    report = evaluate(root)
    assert report == evaluate(root)
    assert report["full_policy_adoption"] == "PROMOTED"
    assert report["hold_register"] == [] and report["alert"] is False
    assert report["deployment"] == report["docker_build"] == report["full_tool_admission"] == "HOLD"
    assert all(p["adoption"] == "PROMOTED_SYSTEM_SOFTWARE_VALIDATION" for p in report["policies"])
    disregarded = [p for p in report["historical_source_pins"] if p["status"] != "PASS"]
    assert len(disregarded) == 1
    assert disregarded[0]["status"] == "DISREGARDED_BY_HUMAN"
    assert disregarded[0]["historical_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("field,value", [
    ("status", "AUTO_APPROVED"), ("deployment", "READY"), ("module_loc_limit", 101),
    ("policy_bundle_sha256", "0" * 64), ("policy_sources", {}), ("scope", "hardware"),
    ("extra_authority", True),
])
def test_promotion_rejects_unapproved_changes(tmp_path: Path, field: str, value) -> None:
    root = support_copy(tmp_path)
    path = root / "policy/promotion.json"
    record = json.loads(path.read_text())
    record[field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        evaluate(root)


def test_promotion_missing_and_undispositioned_pin_fail_closed(tmp_path: Path) -> None:
    root = support_copy(tmp_path)
    record = load_promotion(root, load_profile(root))
    with pytest.raises(ValueError, match="UNDISPOSITIONED_SOURCE_PIN"):
        disposition_pins([{"artifact": "other.zip", "expected_sha256": "0" * 64,
                           "status": "UNAVAILABLE"}], record)
    (root / "policy/promotion.json").unlink()
    with pytest.raises(ValueError, match="ADMISSION_FILE_UNAVAILABLE"):
        evaluate(root)


def test_function_budget_includes_decorators(tmp_path: Path) -> None:
    path = tmp_path / "src/probe.py"
    path.parent.mkdir()
    path.write_text("@decorator\ndef probe():\n" + "    value = 1\n" * 59)
    assert fold_measurements(tmp_path)[0]["max_function_physical_loc"] == 61
    root = support_copy(tmp_path / "host")
    target = root / "src/probe.py"
    target.parent.mkdir()
    target.write_text(path.read_text())
    with pytest.raises(ValueError, match="FUNCTION_CEILING_EXCEEDED"):
        evaluate(root)


@pytest.mark.parametrize("source", ["def broken:\n    pass\n", "value = (\n"])
def test_malformed_source_replaces_prior_pass_receipt(tmp_path: Path, source: str) -> None:
    root = support_copy(tmp_path)
    destination = root / "evidence/ci/phase2/policy_evaluation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"assessment_status": "PASS", "full_policy_adoption": "PROMOTED"}))
    target = root / "src/probe.py"
    target.parent.mkdir()
    target.write_text(source)
    assert main(root) == 1
    report = json.loads(destination.read_text())
    assert report["assessment_status"] == "FAIL" and report["alert"] is True
    assert report["reason_codes"]
    assert all(report[field] == "HOLD" for field in
               ("full_policy_adoption", "full_tool_admission", "docker_build", "deployment"))
