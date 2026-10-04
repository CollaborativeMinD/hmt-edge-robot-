"""REQ-CD5-01/04: separate microSD lab profile; no historical policy rewrite."""
from __future__ import annotations

from typing import Literal

from deployment_contracts import Closed, GitHash
from pydantic import Field, field_validator, model_validator
from target_contracts import Count, Host, Text


class Node(Closed):
    hostname: Host
    model_family: Literal["Raspberry Pi 5", "Raspberry Pi 4 Model B"]
    role: Literal["control_plane", "application_ledger", "backup_restore"]
    disk_bytes: Count
    root_partition_bytes: Count
    baseline_kernel: Text
    baseline_os_full_version: Text
    baseline_tailscale_version: Text
    tailscale_ipv4: Text


class TargetPolicy(Closed):
    schema_version: Literal[1]
    stage: Literal[5]
    baseline_commit: GitHash
    scope: Literal["read_only_target_qualification"]
    source: Literal["OWNER_SCREENSHOT_TRANSCRIPTION"]
    supplied_date: Literal["2026-10-04"]
    storage_medium: Literal["microSD"]
    topology: Literal["single_server_lab"]
    ledger_gib: Literal[8]
    disk_reserve_bytes: Literal[8589934592]
    minimum_memory_kib: Literal[7340032]
    capture_max_age_seconds: Literal[900]
    preserve_tailscale: Literal[True]
    bootstrap: Literal["HOLD"]
    deployment: Literal["HOLD"]
    physical_actuation: Literal["HOLD"]
    nodes: tuple[Node, ...] = Field(min_length=3, max_length=3)

    @field_validator("nodes", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value

    @model_validator(mode="before")
    @classmethod
    def exact_literals(cls, value: object) -> object:
        if isinstance(value, dict):
            for key in ("stage", "ledger_gib", "disk_reserve_bytes", "minimum_memory_kib", "capture_max_age_seconds"):
                if key in value and type(value[key]) is not int:
                    raise ValueError("TARGET_POLICY_INTEGER_REQUIRED")
            if value.get("preserve_tailscale") is not True:
                raise ValueError("TAILSCALE_PRESERVATION_REQUIRED")
        return value

    @model_validator(mode="after")
    def assignments(self) -> TargetPolicy:
        expected = {
            "forge-pi-01": ("control_plane", "Raspberry Pi 5"),
            "forge-pi-02": ("application_ledger", "Raspberry Pi 4 Model B"),
            "forge-pi-03": ("backup_restore", "Raspberry Pi 4 Model B"),
        }
        if {n.hostname: (n.role, n.model_family) for n in self.nodes} != expected or len({n.tailscale_ipv4 for n in self.nodes}) != 3:
            raise ValueError("TARGET_TOPOLOGY_MISMATCH")
        if any(n.root_partition_bytes >= n.disk_bytes for n in self.nodes):
            raise ValueError("TARGET_PARTITION_BOUNDS")
        return self
