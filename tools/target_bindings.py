"""REQ-CD5-01: complete field-to-governed-subtype linkage for target handoffs."""
from __future__ import annotations

from pathlib import Path

from target_contracts import Capture, Probe, Snapshot
from target_owner import ImageReference, OwnerInventory, OwnerNode
from target_profile import Node, TargetPolicy
from target_receipts import InventoryReceipt, Rejection

MODELS = (Capture, Probe, Snapshot, ImageReference, OwnerInventory, OwnerNode, Node, TargetPolicy, InventoryReceipt, Rejection)
GROUPS = {
    "IdentifierField": {"hostname", "name"},
    "PhysicalMetricField": {"memory_total_kib", "disk_bytes", "root_partition_bytes", "root_total_bytes", "root_available_bytes", "memory_reported", "memory_available_reported", "root_available_reported", "root_used_percent_reported", "zram_bytes"},
    "PhysicalBoundField": {"ledger_gib", "disk_reserve_bytes", "minimum_memory_kib", "capture_max_age_seconds"},
    "TelemetryIntegrityField": {"policy_hash", "collector_hash", "sha256", "receipt_hash"},
    "EvidenceQualityField": {"started_at", "finished_at", "capture_timestamp", "assessed_at"},
    "ProvenanceField": {"origin", "source", "supplied_date", "boot_id"},
    "EvidenceField": {"probes", "snapshot", "output", "captures"},
    "EvidenceReferenceField": {"filename", "screenshots"},
    "ArtifactReferenceField": {"baseline_commit"},
    "TopologyReferenceField": {"topology", "nodes", "tailscale_ipv4"},
    "DeploymentConstraintField": {"scope", "preserve_tailscale", "bootstrap", "deployment", "physical_actuation", "authority"},
    "ValidationStatusField": {"status", "reason_code", "reason_codes", "target_qualification", "inventory_status", "alert"},
    "VocabularyBindingField": {"schema_version"},
    "RuntimeControlField": {"role", "stage"},
    "DomainDescriptorField": {"model", "model_family", "kernel", "baseline_kernel", "architecture", "userspace_bits", "os_id", "os_version", "os_full_version", "baseline_os_full_version", "root_device", "root_fstype", "var_on_root", "tailscale_version", "baseline_tailscale_version", "storage_medium"},
}


def bindings() -> list[dict[str, str]]:
    result = []
    for model in MODELS:
        for name in model.model_fields:
            types = [subtype for subtype, names in GROUPS.items() if name in names]
            if len(types) != 1:
                raise ValueError("TARGET_FIELD_BINDING_UNDEFINED")
            result.append({"contract": model.__name__, "field": name, "subtype": types[0], "basis": "Strict target contract; no actuation or deployment authority"})
    return result


def verify(root: Path) -> None:
    from target_io import read_json

    value = read_json(root / "docs/cd/target-field-bindings.json")
    if value != {"bindings": bindings()}:
        raise ValueError("TARGET_FIELD_BINDING_DRIFT")
    allowed = read_json(root / "docs/source_provenance.json")["upstream_subtype_classes"]
    if any(b["subtype"] not in allowed for b in value["bindings"]):
        raise ValueError("TARGET_FIELD_SUBTYPE_UNGOVERNED")
