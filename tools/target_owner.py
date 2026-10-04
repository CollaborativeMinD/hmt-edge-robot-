"""REQ-CD5-01: owner screenshots are historical host evidence, not live captures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from ci_admission import ROOT, digest
from deployment_contracts import Closed, Hash
from pydantic import Field, field_validator
from target_contracts import Host, Text
from target_io import bind, read_json


class ImageReference(Closed):
    filename: Text
    sha256: Hash


class OwnerNode(Closed):
    hostname: Host
    kernel: Text
    os_full_version: Text
    architecture: Literal["aarch64"]
    userspace_bits: Literal[64]
    disk_bytes: int = Field(gt=0)
    root_partition_bytes: int = Field(gt=0)
    root_fstype: Literal["ext4"]
    memory_reported: Text
    memory_available_reported: Text
    root_available_reported: Text
    root_used_percent_reported: int = Field(ge=0, le=100)
    zram_bytes: Literal[2147483648]
    tailscale_version: Text
    tailscale_ipv4: Text
    screenshots: tuple[ImageReference, ...] = Field(min_length=2, max_length=2)

    @field_validator("screenshots", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value


class OwnerInventory(Closed):
    schema_version: Literal[1]
    origin: Literal["OWNER_SCREENSHOT_TRANSCRIPTION"]
    supplied_date: Literal["2026-10-04"]
    capture_timestamp: None
    nodes: tuple[OwnerNode, ...] = Field(min_length=3, max_length=3)
    target_qualification: Literal["HOLD"]
    deployment: Literal["HOLD"]

    @field_validator("nodes", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value


def evaluate(root: Path) -> dict:
    policy, collector_hash = bind(root)
    owner = OwnerInventory.model_validate_json(json.dumps(read_json(root / "docs/cd/owner-inventory.json")))
    if {n.hostname for n in owner.nodes} != {n.hostname for n in policy.nodes}:
        raise ValueError("OWNER_NODE_SET_MISMATCH")
    for observed in owner.nodes:
        node = next(n for n in policy.nodes if n.hostname == observed.hostname)
        actual = (observed.kernel, observed.os_full_version, observed.disk_bytes, observed.root_partition_bytes, observed.tailscale_version, observed.tailscale_ipv4)
        expected = (node.baseline_kernel, node.baseline_os_full_version, node.disk_bytes, node.root_partition_bytes, node.baseline_tailscale_version, node.tailscale_ipv4)
        if actual != expected:
            raise ValueError("OWNER_TRANSCRIPTION_POLICY_DIVERGENCE")
    return {"status": "PASS", "owner_inventory": "BOUND", "target_qualification": "HOLD", "deployment": "HOLD", "policy_hash": digest(root / "policy/target.json"), "collector_hash": collector_hash, "reason_codes": ["HOST_BASELINE_BOUND", "LIVE_TARGET_CAPTURE_REQUIRED", "RUNTIME_TRIALS_REQUIRED"]}


if __name__ == "__main__":
    print(json.dumps(evaluate(ROOT)))
