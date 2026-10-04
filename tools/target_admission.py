"""REQ-CD5-03/04: admit inventory consistency; keep unobserved runtime gates held."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ci_admission import digest
from deployment_receipts import content_hash
from target_commands import COMMANDS, REQUIRED
from target_contracts import Capture
from target_io import bind, read_json
from target_profile import TargetPolicy
from target_receipts import InventoryReceipt
from target_snapshot import storage

RUNTIME_HOLDS = (
    "ARTIFACT_QUALIFICATION_REQUIRED", "PRIVATE_SIGNING_REQUIRED", "PROTECTED_PROMOTION_REQUIRED",
    "K3S_CLUSTER_READY_UNOBSERVED", "CNI_ENFORCEMENT_UNOBSERVED", "RUNTIME_READINESS_UNOBSERVED",
    "SINGLE_WRITER_FENCING_UNOBSERVED", "DISK_PRESSURE_TRIAL_UNOBSERVED",
    "BACKUP_RESTORE_TRIAL_UNOBSERVED", "PRIVATE_ACCESS_TRIAL_UNOBSERVED", "NATIVE_RESOURCE_TRIAL_UNOBSERVED",
)


def check_capture(capture: Capture, policy: TargetPolicy, policy_hash: str, collector_hash: str, now: datetime) -> None:
    # Formula Family FF-V6-LOGIC-01 / LOGIC-EQ-04: all admission predicates must hold.
    if capture.policy_hash != policy_hash or capture.collector_hash != collector_hash or capture.baseline_commit != policy.baseline_commit:
        raise ValueError("TARGET_IDENTITY_MISMATCH")
    if now.utcoffset() != timedelta(0) or not timedelta(0) <= now - capture.finished_at <= timedelta(seconds=policy.capture_max_age_seconds):
        raise ValueError("TARGET_CAPTURE_STALE_OR_FUTURE")
    probes = {p.name: p for p in capture.probes}
    if set(probes) != set(COMMANDS) or any(probes[name].status != "PASS" or probes[name].reason_code != "COMMAND_COMPLETED" for name in REQUIRED):
        raise ValueError("TARGET_PROBE_INCOMPLETE")
    host = capture.snapshot
    raw = {name: probe.output.strip() for name, probe in probes.items()}
    for name in ("hostname", "kernel", "architecture", "userspace_bits", "tailscale_ipv4"):
        if raw[name] != str(getattr(host, name)):
            raise ValueError("TARGET_PROBE_SNAPSHOT_MISMATCH")
    if raw["tailscale_version"].splitlines()[0] != host.tailscale_version or storage(raw["blocks"]) != (host.disk_bytes, host.root_partition_bytes):
        raise ValueError("TARGET_PROBE_SNAPSHOT_MISMATCH")
    node = next(n for n in policy.nodes if n.hostname == host.hostname)
    if not host.model.startswith(node.model_family + " ") or host.tailscale_ipv4 != node.tailscale_ipv4 or host.disk_bytes != node.disk_bytes or host.root_partition_bytes != node.root_partition_bytes:
        raise ValueError("TARGET_NODE_BASELINE_MISMATCH")
    if host.kernel != node.baseline_kernel or host.os_full_version != node.baseline_os_full_version or host.tailscale_version != node.baseline_tailscale_version:
        raise ValueError("TARGET_VERSION_DRIFT_REQUIRES_REVIEW")
    if host.memory_total_kib < policy.minimum_memory_kib or host.root_available_bytes < policy.disk_reserve_bytes + policy.ledger_gib * 2**30:
        raise ValueError("TARGET_CAPACITY_NOT_ADMITTED")


def evaluate(root: Path, paths: tuple[Path, ...], now: datetime | None = None) -> dict[str, Any]:
    policy, collector_hash = bind(root)
    if len(paths) != 3 or len({p.resolve() for p in paths}) != 3:
        raise ValueError("THREE_DISTINCT_CAPTURE_FILES_REQUIRED")
    now = now or datetime.now(timezone.utc)
    captures = tuple(Capture.model_validate_json(json.dumps(read_json(path))) for path in paths)
    if {c.snapshot.hostname for c in captures} != {n.hostname for n in policy.nodes}:
        raise ValueError("THREE_DISTINCT_HOSTS_REQUIRED")
    for capture in captures:
        check_capture(capture, policy, digest(root / "policy/target.json"), collector_hash, now)
    holds = list(RUNTIME_HOLDS)
    for capture in sorted(captures, key=lambda c: c.snapshot.hostname):
        service = "k3s_server" if capture.snapshot.hostname == "forge-pi-01" else "k3s_agent"
        opposite = "k3s_agent" if service == "k3s_server" else "k3s_server"
        probes = {p.name: p for p in capture.probes}
        if probes[service].status != "PASS" or probes[service].output.strip() != "active":
            holds.append("K3S_ASSIGNED_SERVICE_UNOBSERVED:" + capture.snapshot.hostname)
        if probes[opposite].status == "PASS" and probes[opposite].output.strip() == "active":
            holds.append("K3S_ROLE_CONFLICT:" + capture.snapshot.hostname)
    payload = {"schema_version": 1, "inventory_status": "PASS", "target_qualification": "HOLD", "deployment": "HOLD", "physical_actuation": "HOLD", "authority": "INVENTORY_CONSISTENCY_ONLY", "assessed_at": now.isoformat(), "policy_hash": digest(root / "policy/target.json"), "collector_hash": collector_hash, "captures": {c.snapshot.hostname: content_hash(c.model_dump(mode="json")) for c in sorted(captures, key=lambda c: c.snapshot.hostname)}, "reason_codes": holds, "alert": True}
    return InventoryReceipt.model_validate_json(json.dumps({**payload, "receipt_hash": content_hash(payload)})).model_dump(mode="json")


def verify_receipt(root: Path, paths: tuple[Path, ...], receipt: dict[str, Any], now: datetime) -> None:
    expected = evaluate(root, paths, now)
    if receipt != expected:
        raise ValueError("TARGET_RECEIPT_STALE_OR_FORGED")
