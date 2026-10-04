"""REQ-CD5-01/03/04: strict evidence, freshness, provenance and authority denial."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from target_admission import RUNTIME_HOLDS, evaluate, verify_receipt
from target_contracts import Capture, Probe, Snapshot
from target_io import bind
from target_owner import OwnerInventory
from target_profile import TargetPolicy
from target_test_support import NOW, ROOT, captures, make_root, payloads


def test_inventory_does_not_grant_runtime_authority(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    paths = captures(root)
    result = evaluate(root, paths, NOW)
    assert result["inventory_status"] == "PASS" and result["deployment"] == "HOLD"
    assert set(RUNTIME_HOLDS) <= set(result["reason_codes"])
    assert evaluate(root, tuple(reversed(paths)), NOW) == result
    verify_receipt(root, paths, result, NOW)
    with pytest.raises(ValueError, match="FORGED"):
        verify_receipt(root, paths, {**result, "deployment": "PASS"}, NOW)
    for delta in (timedelta(seconds=901), timedelta(seconds=-1)):
        with pytest.raises(ValueError, match="STALE_OR_FUTURE"):
            evaluate(root, paths, NOW + delta)


@pytest.mark.parametrize("field,value", [("disk_bytes", "63864569856"), ("userspace_bits", 64.0), ("var_on_root", 1), ("memory_total_kib", True), ("architecture", "armv7l"), ("root_fstype", "vfat"), ("tailscale_ipv4", "192.168.1.1"), ("root_available_bytes", -1), ("root_total_bytes", 2**50), ("hostname", "other"), ("secret", "x")])
def test_snapshot_rejects_coercion_and_drift(field: str, value: object) -> None:
    host = payloads(ROOT)[0]["snapshot"]
    with pytest.raises(ValueError):
        Snapshot.model_validate({**host, field: value})


@pytest.mark.parametrize("field,value", [("schema_version", True), ("stage", 5.0), ("preserve_tailscale", 1), ("bootstrap", "PASS"), ("storage_medium", "SSD"), ("ledger_gib", 16), ("disk_reserve_bytes", "8589934592"), ("capture_max_age_seconds", 9999), ("nodes", []), ("scope", "deploy"), ("secret", "x")])
def test_profile_rejects_authority_and_coercion(field: str, value: object) -> None:
    data = json.loads((ROOT / "policy/target.json").read_text())
    with pytest.raises(ValueError):
        TargetPolicy.model_validate_json(json.dumps({**data, field: value}))


@pytest.mark.parametrize("field,value", [("origin", "FIXTURE"), ("deployment", "PASS"), ("boot_id", "------------------------------------"), ("started_at", "2026-10-04T18:30:01Z"), ("started_at", "2026-10-04T18:00:00Z"), ("finished_at", "2026-10-04T19:30:00+01:00"), ("finished_at", "2026-10-04T18:30:00"), ("schema_version", "1")])
def test_capture_rejects_origin_and_time(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        Capture.model_validate_json(json.dumps({**payloads(ROOT)[0], field: value}))


def test_profile_and_probe_coupling() -> None:
    data = json.loads((ROOT / "policy/target.json").read_text())
    for patch in (dict(role="backup_restore"), dict(tailscale_ipv4=data["nodes"][1]["tailscale_ipv4"]), dict(root_partition_bytes=2**40)):
        altered = json.loads(json.dumps(data))
        altered["nodes"][0].update(patch)
        with pytest.raises(ValueError):
            TargetPolicy.model_validate_json(json.dumps(altered))
    with pytest.raises(ValueError):
        Probe(name="kernel", status="PASS", output="x", reason_code="COMMAND_TIMEOUT")
    value = payloads(ROOT)[0]
    value["probes"].append(value["probes"][0])
    with pytest.raises(ValueError):
        Capture.model_validate_json(json.dumps(value))
    owner = json.loads((ROOT / "docs/cd/owner-inventory.json").read_text())
    assert OwnerInventory.model_validate_json(json.dumps(owner)).capture_timestamp is None
    assert bind(ROOT)[0].storage_medium == "microSD"
