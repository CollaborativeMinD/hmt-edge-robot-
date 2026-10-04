"""Synthetic local captures for rejection tests; never deployment evidence."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ci_admission import digest
from target_commands import COMMANDS, REQUIRED
from target_io import bind

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 4, 18, 30, tzinfo=timezone.utc)


def make_root(path: Path) -> Path:
    for directory in ("tools", "policy", "docs"):
        shutil.copytree(ROOT / directory, path / directory)
    return path


def blocks(disk: int, partition: int) -> dict[str, Any]:
    return {"blockdevices": [{"name": "mmcblk0", "size": disk, "type": "disk", "fstype": None, "mountpoints": [None], "children": [{"name": "mmcblk0p2", "size": partition, "type": "part", "fstype": "ext4", "mountpoints": ["/"]}]}]}


def payloads(root: Path) -> list[dict[str, Any]]:
    policy, source_hash = bind(root)
    result = []
    for index, node in enumerate(policy.nodes):
        host = dict(hostname=node.hostname, model=node.model_family + " Rev 1.0", kernel=node.baseline_kernel, architecture="aarch64", userspace_bits=64, os_id="debian", os_version="13", os_full_version=node.baseline_os_full_version, memory_total_kib=8000000, disk_bytes=node.disk_bytes, root_partition_bytes=node.root_partition_bytes, root_total_bytes=node.root_partition_bytes - 2**30, root_available_bytes=30 * 2**30, root_device="/dev/mmcblk0p2", root_fstype="ext4", var_on_root=True, tailscale_version=node.baseline_tailscale_version, tailscale_ipv4=node.tailscale_ipv4)
        outputs = {k: str(host[k]) for k in REQUIRED if k != "blocks"}
        outputs["blocks"] = json.dumps(blocks(node.disk_bytes, node.root_partition_bytes))
        probes = [dict(name=k, status="PASS" if k in REQUIRED else "FAIL", output=outputs.get(k, ""), reason_code="COMMAND_COMPLETED" if k in REQUIRED else "COMMAND_UNAVAILABLE") for k in COMMANDS]
        result.append(dict(schema_version=1, origin="LOCAL_READ_ONLY_COLLECTOR", policy_hash=digest(root / "policy/target.json"), collector_hash=source_hash, baseline_commit=policy.baseline_commit, started_at="2026-10-04T18:29:50+00:00", finished_at="2026-10-04T18:30:00+00:00", boot_id=f"12345678-1234-1234-1234-12345678900{index}", probes=probes, snapshot=host, deployment="HOLD"))
    return result


def captures(root: Path, values: list[dict[str, Any]] | None = None) -> tuple[Path, ...]:
    paths = []
    for i, value in enumerate(values or payloads(root)):
        path = root / f"capture-{i}.json"
        path.write_text(json.dumps(value))
        paths.append(path)
    return tuple(paths)
