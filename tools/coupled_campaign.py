"""Bounded, real composed SIL campaign and host resource measurements."""

from __future__ import annotations

import json
import resource
import secrets
import statistics
import tempfile
import time
from pathlib import Path

import polars as pl

from hmt_edge_robot.contracts import MotionRequest
from hmt_edge_robot.runtime import RobotCell


def run() -> dict:
    durations = []
    token = secrets.token_hex(24)
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "cell.db"
        cell = RobotCell(database, token)
        for seq in range(32):
            start = time.perf_counter()
            session = cell.access.login("operator", token, cell.clock())
            cell.observe_simulation(seq)
            now = cell.clock()
            order = MotionRequest(
                request_id=f"coupled-{seq}",
                operator_id="operator",
                session_id=session,
                policy_epoch=1,
                target_mm=(10.0, 20.0, 10.0),
                speed_mps=0.1,
                issued_at=now,
                expires_at=now + 2.0,
            )
            planned = cell.orchestrator.submit(order)
            outcome = cell.orchestrator.run_next()
            if planned.state.value != "PLANNED" or outcome.state.value != "SUCCEEDED":
                raise RuntimeError("COUPLED_MISSION_FAILED")
            cell.access.revoke(session)
            durations.append((time.perf_counter() - start) * 1000)
        events = cell.ledger.verify()
        exported = cell.analytics.export_parquet(Path(directory) / "events.parquet")
        parquet = pl.read_parquet(Path(directory) / "events.parquet")
        if exported != events or parquet.height != events or cell.driver.moves != 32:
            raise RuntimeError("COUPLED_EVIDENCE_DIVERGED")
        cell.close()
        with_read = RobotCell(database, token, read_only=True)
        replayed = with_read.ledger.verify()
        with_read.close()
    p95 = sorted(durations)[int(0.95 * (len(durations) - 1))]
    peak_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return {
        "status": "PASS" if p95 < 100 and peak_mib < 512 and replayed == events else "FAIL",
        "mode": "SIL",
        "cycles": 32,
        "events": events,
        "parquet_records": exported,
        "p95_cycle_ms": p95,
        "median_cycle_ms": statistics.median(durations),
        "peak_host_rss_mib": peak_mib,
        "limits": {"p95_ms": 100, "host_rss_mib": 512},
        "scope": "Observed Linux host campaign; not worst-case execution time or target firmware proof",
    }


if __name__ == "__main__":
    result = run()
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/coupled_campaign.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)
