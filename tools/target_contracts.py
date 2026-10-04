"""REQ-CD5-01/03: strict local-host evidence; never deployment authority."""
from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network
from typing import Annotated, Literal
from uuid import UUID

from deployment_contracts import Closed, GitHash, Hash
from pydantic import Field, field_validator, model_validator

Host = Literal["forge-pi-01", "forge-pi-02", "forge-pi-03"]
Text = Annotated[str, Field(min_length=1, max_length=256)]
Count = Annotated[int, Field(ge=1, le=2**50)]


class Snapshot(Closed):
    hostname: Host
    model: Text
    kernel: Text
    architecture: Literal["aarch64"]
    userspace_bits: Literal[64]
    os_id: Literal["debian"]
    os_version: Literal["13"]
    os_full_version: Text
    memory_total_kib: Count
    disk_bytes: Count
    root_partition_bytes: Count
    root_total_bytes: Count
    root_available_bytes: int = Field(ge=0, le=2**50)
    root_device: Literal["/dev/mmcblk0p2"]
    root_fstype: Literal["ext4"]
    var_on_root: Literal[True]
    tailscale_version: Text
    tailscale_ipv4: Text

    @field_validator("userspace_bits", "var_on_root", mode="before")
    @classmethod
    def exact_literals(cls, value: object) -> object:
        if type(value) not in (int, bool) or value is False:
            raise ValueError("TARGET_LITERAL_TYPE")
        if value == 64 and type(value) is not int:
            raise ValueError("TARGET_BITS_TYPE")
        if value == 1 and type(value) is not bool:
            raise ValueError("TARGET_BOOLEAN_TYPE")
        return value

    @model_validator(mode="after")
    def storage_and_network(self) -> Snapshot:
        if not self.root_available_bytes <= self.root_total_bytes <= self.root_partition_bytes < self.disk_bytes:
            raise ValueError("TARGET_STORAGE_INCONSISTENT")
        if IPv4Address(self.tailscale_ipv4) not in IPv4Network("100.64.0.0/10"):
            raise ValueError("TAILNET_ADDRESS_REQUIRED")
        return self


class Probe(Closed):
    name: Text
    status: Literal["PASS", "FAIL"]
    output: str = Field(max_length=65536)
    reason_code: Literal["COMMAND_COMPLETED", "COMMAND_FAILED", "COMMAND_UNAVAILABLE", "COMMAND_TIMEOUT", "COMMAND_OUTPUT_LIMIT"]

    @model_validator(mode="after")
    def outcome(self) -> Probe:
        if (self.status == "PASS") != (self.reason_code == "COMMAND_COMPLETED"):
            raise ValueError("PROBE_OUTCOME_CONTRADICTION")
        return self


class Capture(Closed):
    schema_version: Literal[1]
    origin: Literal["LOCAL_READ_ONLY_COLLECTOR"]
    policy_hash: Hash
    collector_hash: Hash
    baseline_commit: GitHash
    started_at: datetime
    finished_at: datetime
    boot_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    probes: tuple[Probe, ...] = Field(min_length=1, max_length=16)
    snapshot: Snapshot
    deployment: Literal["HOLD"]

    @field_validator("probes", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def utc_transport(cls, value: object) -> object:
        return datetime.fromisoformat(value) if type(value) is str else value

    @model_validator(mode="after")
    def time_window(self) -> Capture:
        if str(UUID(self.boot_id)) != self.boot_id:
            raise ValueError("TARGET_BOOT_ID_INVALID")
        if any(t.utcoffset() != timedelta(0) for t in (self.started_at, self.finished_at)):
            raise ValueError("TARGET_UTC_REQUIRED")
        if not timedelta(0) <= self.finished_at - self.started_at <= timedelta(seconds=120):
            raise ValueError("TARGET_CAPTURE_WINDOW")
        if len({p.name for p in self.probes}) != len(self.probes):
            raise ValueError("TARGET_DUPLICATE_PROBE")
        return self
