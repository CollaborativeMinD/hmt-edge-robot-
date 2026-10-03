"""REQ-CD4-02: execute the installed composition in a restricted SIL container."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import secrets
from pathlib import Path

import polars as pl

from hmt_edge_robot.cli_demonstration import demonstrate
from hmt_edge_robot.runtime import RobotCell


def run(directory: Path) -> dict:
    token = secrets.token_hex(24)
    database = directory / "cell.db"
    cell = RobotCell(database, token)
    try:
        result = demonstrate(cell, token)
        if result["outcome"] is None or result["outcome"]["state"] != "SUCCEEDED":
            raise ValueError("INSTALLED_MISSION_FAILED")
        events = cell.ledger.verify()
        exported = cell.analytics.export_parquet(directory / "events.parquet")
        if exported != events or pl.read_parquet(directory / "events.parquet").height != events:
            raise ValueError("INSTALLED_ANALYTICS_DIVERGED")
        cell.orchestrator.stop()
        moves = cell.driver.moves
        session = cell.access.login("operator", token, cell.clock())
        cell.resident_tool("inspect", session, "operator")
        if cell.driver.moves != moves or not cell.orchestrator.stopped:
            raise ValueError("RESIDENT_STOP_BOUNDARY_FAILED")
        events = cell.ledger.verify()
    finally:
        cell.close()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    reader = RobotCell(database, token, read_only=True)
    try:
        replayed = reader.ledger.verify()
    finally:
        reader.close()
    if replayed != events or hashlib.sha256(database.read_bytes()).hexdigest() != before:
        raise ValueError("INSTALLED_REPLAY_MUTATED")
    packages = {d.metadata["Name"].lower().replace("_", "-"): d.version
                for d in importlib.metadata.distributions()}
    if any(name in packages for name in ("pytest", "ruff", "pyrefly", "scaffoldctl", "marimo")):
        raise ValueError("DEVELOPMENT_TOOLS_IN_RUNTIME")
    return {"status": "PASS", "mode": "SIL", "platform": platform.machine(),
        "uid": os.getuid(), "events": events, "replayed": replayed,
        "exported": exported, "simulated_moves": moves, "paid_calls": 0,
        "packages": packages, "resident_stopped": True}


if __name__ == "__main__":
    print(json.dumps(run(Path("/data")), allow_nan=False))
