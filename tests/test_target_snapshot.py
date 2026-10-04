"""REQ-CD5-02: root-device and memory observations must survive parsing intact."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import target_snapshot
from target_contracts import Probe
from target_test_support import ROOT, blocks, payloads


@pytest.mark.parametrize("change", ["two_disks", "name", "root", "fstype", "size", "duplicate_root"])
def test_storage_ambiguity_rejected(change: str) -> None:
    value = blocks(63864569856, 63319310336)
    disk = value["blockdevices"][0]
    if change == "two_disks":
        value["blockdevices"].append(disk)
    elif change == "name":
        disk["name"] = "sda"
    elif change == "root":
        disk["children"][0]["mountpoints"] = ["/other"]
    elif change == "fstype":
        disk["children"][0]["fstype"] = "vfat"
    elif change == "size":
        disk["size"] = str(disk["size"])
    else:
        disk["children"].append(disk["children"][0])
    with pytest.raises(ValueError):
        target_snapshot.storage(json.dumps(value))


def test_host_file_and_os_release_bounds(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"model\x00\n")
    assert target_snapshot.read_host(str(path)) == "model"
    path.write_bytes(b"x" * 16385)
    with pytest.raises(ValueError):
        target_snapshot.read_host(str(path))
    assert target_snapshot.os_fields('# comment\n\nID=debian\nVERSION="13 (trixie)"')["ID"] == "debian"
    for value in ("ID=debian\nID=ubuntu", "ID=a b"):
        with pytest.raises(ValueError):
            target_snapshot.os_fields(value)


def test_snapshot_uses_real_units_and_root_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    value = payloads(ROOT)[0]
    readings = {"/etc/os-release": 'ID=debian\nVERSION_ID=13\nDEBIAN_VERSION_FULL=13.5', "/proc/meminfo": 'MemTotal: 8000000 kB', "/proc/device-tree/model": 'Raspberry Pi 5 Rev 1.0'}
    monkeypatch.setattr(target_snapshot, "read_host", lambda path: readings[path])
    monkeypatch.setattr(target_snapshot, "os", SimpleNamespace(statvfs=lambda _: SimpleNamespace(f_blocks=50 * 2**30, f_frsize=1, f_bavail=30 * 2**30), stat=lambda _: SimpleNamespace(st_dev=1)))
    probes = tuple(Probe.model_validate(p) for p in value["probes"])
    assert target_snapshot.snapshot(probes).memory_total_kib == 8000000
    readings["/proc/meminfo"] = "MemTotal: 8000000 MB"
    with pytest.raises(ValueError):
        target_snapshot.snapshot(probes)
