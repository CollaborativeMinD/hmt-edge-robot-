"""REQ-CD5-02: parse machine observations without inferring runtime qualification."""
from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any

from target_contracts import Probe, Snapshot
from truth_serum_runtime.gates.data_parse import loads_json


def read_host(path: str) -> str:
    with Path(path).open("rb") as stream:
        data = stream.read(16385)
    if len(data) > 16384:
        raise ValueError("HOST_FILE_BOUNDS")
    return data.decode("utf-8").strip("\x00\n")


def os_fields(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        parts = shlex.split(value)
        if key in result or len(parts) != 1:
            raise ValueError("OS_RELEASE_INVALID")
        result[key] = parts[0]
    return result


def storage(raw: str) -> tuple[int, int]:
    value = loads_json(raw)
    devices = value["blockdevices"]
    if len(devices) != 1:
        raise ValueError("BLOCK_DEVICE_AMBIGUOUS")
    disk = devices[0]
    if disk["name"] != "mmcblk0" or disk["type"] != "disk":
        raise ValueError("MICROSD_DEVICE_REQUIRED")
    roots = [part for part in disk["children"] if "/" in (part["mountpoints"] or [])]
    if len(roots) != 1 or roots[0]["name"] != "mmcblk0p2" or roots[0]["type"] != "part" or roots[0]["fstype"] != "ext4":
        raise ValueError("EXT4_ROOT_PARTITION_REQUIRED")
    if type(disk["size"]) is not int or type(roots[0]["size"]) is not int:
        raise ValueError("BLOCK_SIZE_INTEGER_REQUIRED")
    return disk["size"], roots[0]["size"]


def snapshot(probes: tuple[Probe, ...]) -> Snapshot:
    output = {p.name: p.output.strip() for p in probes}
    disk, partition = storage(output["blocks"])
    release = os_fields(read_host("/etc/os-release"))
    memory = [line.split() for line in read_host("/proc/meminfo").splitlines() if line.startswith("MemTotal:")]
    if len(memory) != 1 or len(memory[0]) != 3 or memory[0][2] != "kB":
        raise ValueError("MEMORY_OBSERVATION_REQUIRED")
    stats = os.statvfs("/")
    values: dict[str, Any] = {
        "hostname": output["hostname"], "kernel": output["kernel"],
        "model": read_host("/proc/device-tree/model"), "architecture": output["architecture"],
        "userspace_bits": int(output["userspace_bits"]), "os_id": release["ID"],
        "os_version": release["VERSION_ID"], "os_full_version": release["DEBIAN_VERSION_FULL"],
        "memory_total_kib": int(memory[0][1]), "disk_bytes": disk,
        "root_partition_bytes": partition, "root_total_bytes": stats.f_blocks * stats.f_frsize,
        "root_available_bytes": stats.f_bavail * stats.f_frsize, "root_device": "/dev/mmcblk0p2",
        "root_fstype": "ext4", "var_on_root": os.stat("/").st_dev == os.stat("/var").st_dev,
        "tailscale_version": output["tailscale_version"].splitlines()[0],
        "tailscale_ipv4": output["tailscale_ipv4"],
    }
    return Snapshot.model_validate(values)
