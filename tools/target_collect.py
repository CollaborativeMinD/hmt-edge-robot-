"""REQ-CD5-02: explicit operator-run local inventory; no SSH or bootstrap calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ci_admission import ROOT, digest
from target_commands import COMMANDS, REQUIRED, execute
from target_contracts import Capture
from target_io import atomic_write, bind, output_path
from target_snapshot import read_host, snapshot


def collect(root: Path, destination: Path) -> int:
    destination = output_path(root, destination)
    atomic_write(destination, {"status": "FAIL", "deployment": "HOLD", "reason_codes": ["CAPTURE_INCOMPLETE"], "alert": True})
    try:
        policy, collector_hash = bind(root)
        started = datetime.now(timezone.utc)
        boot = read_host("/proc/sys/kernel/random/boot_id")
        probes = tuple(execute(name) for name in COMMANDS)
        if any(p.status != "PASS" for p in probes if p.name in REQUIRED):
            raise ValueError("REQUIRED_HOST_PROBE_FAILED")
        host = snapshot(probes)
        if read_host("/proc/sys/kernel/random/boot_id") != boot:
            raise ValueError("HOST_REBOOT_DURING_CAPTURE")
        capture = Capture(schema_version=1, origin="LOCAL_READ_ONLY_COLLECTOR", policy_hash=digest(root / "policy/target.json"), collector_hash=collector_hash, baseline_commit=policy.baseline_commit, started_at=started, finished_at=datetime.now(timezone.utc), boot_id=boot, probes=probes, snapshot=host, deployment="HOLD")
        atomic_write(destination, capture.model_dump(mode="json"))
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, TimeoutError):
        failure: dict[str, Any] = {"status": "FAIL", "deployment": "HOLD", "reason_codes": ["TARGET_COLLECTION_FAILED"], "alert": True}
        atomic_write(destination, failure)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return collect(ROOT, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
