"""REQ-CD5-03: reject edited, replayed, incomplete and contradictory host evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from target_admission import evaluate
from target_contracts import Capture
from target_owner import evaluate as owner_evaluate
from target_test_support import NOW, ROOT, captures, make_root, payloads


@pytest.mark.parametrize("field,value", [("policy_hash", "a" * 64), ("collector_hash", "b" * 64), ("baseline_commit", "c" * 40)])
def test_identity_binding(tmp_path: Path, field: str, value: str) -> None:
    root = make_root(tmp_path)
    values = payloads(root)
    values[0][field] = value
    with pytest.raises(ValueError, match="IDENTITY"):
        evaluate(root, captures(root, values), NOW)


@pytest.mark.parametrize("change", ["missing_probe", "failed_probe", "changed_output", "changed_block", "wrong_model", "wrong_ip", "kernel_drift", "os_drift", "tailscale_drift", "small_memory", "disk_pressure", "duplicate_host"])
def test_admission_rejects_unsafe_capture(tmp_path: Path, change: str) -> None:
    root = make_root(tmp_path)
    values = payloads(root)
    host, probes = values[0]["snapshot"], values[0]["probes"]
    if change == "missing_probe":
        probes.pop()
    elif change == "failed_probe":
        probes[0].update(status="FAIL", reason_code="COMMAND_FAILED")
    elif change == "changed_output":
        probes[0]["output"] = "forge-pi-03"
    elif change == "changed_block":
        host["disk_bytes"] += 1
    elif change == "wrong_model":
        host["model"] = "Raspberry Pi 4 Model B Rev 1.0"
    elif change == "wrong_ip":
        host["tailscale_ipv4"] = probes[6]["output"] = "100.64.0.1"
    elif change == "kernel_drift":
        host["kernel"] = probes[1]["output"] = "other"
    elif change == "os_drift":
        host["os_full_version"] = "13.6"
    elif change == "tailscale_drift":
        host["tailscale_version"] = probes[5]["output"] = "1.0"
    elif change == "small_memory":
        host["memory_total_kib"] = 1024
    elif change == "disk_pressure":
        host["root_available_bytes"] = 1
    else:
        values[1] = values[0]
    with pytest.raises(ValueError):
        evaluate(root, captures(root, values), NOW)


def test_service_role_conflicts_and_absence_are_holds(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    values = payloads(root)
    for value in values:
        for probe in value["probes"]:
            if probe["name"] in ("k3s_server", "k3s_agent"):
                probe.update(status="PASS", reason_code="COMMAND_COMPLETED", output="active")
    result = evaluate(root, captures(root, values), NOW)
    assert result["deployment"] == "HOLD"
    assert sum(code.startswith("K3S_ROLE_CONFLICT:") for code in result["reason_codes"]) == 3
    paths = captures(root)
    for bad in (paths[:2], (paths[0], paths[0], paths[1])):
        with pytest.raises(ValueError):
            evaluate(root, bad, NOW)


def test_owner_transcription_and_strict_schema(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    assert owner_evaluate(root)["owner_inventory"] == "BOUND"
    data = json.loads((root / "docs/cd/owner-inventory.json").read_text())
    data["nodes"][0]["kernel"] = "wrong"
    (root / "docs/cd/owner-inventory.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="SOURCE_DRIFT"):
        owner_evaluate(root)
    capture = Capture.model_validate_json(json.dumps(payloads(ROOT)[0]))
    assert capture.snapshot.hostname == "forge-pi-01"
