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


def features(directory: Path) -> dict:
    import importlib
    import lzma
    import socket
    import ssl
    import uuid

    import cv2
    import joblib
    import numpy as np
    from sklearn.linear_model import LinearRegression

    payload = b"HMT compressed ledger fixture"
    if lzma.decompress(lzma.compress(payload)) != payload:
        raise ValueError("RUNTIME_LZMA_FAILED")
    for value in (uuid.uuid1(), uuid.uuid4(), uuid.uuid5(uuid.NAMESPACE_DNS, "localhost")):
        if uuid.UUID(str(value)) != value:
            raise ValueError("RUNTIME_UUID_FAILED")
    path = directory / "model.xz"
    joblib.dump({"data": payload}, path, compress=("xz", 1))
    if joblib.load(path) != {"data": payload}:
        raise ValueError("RUNTIME_JOBLIB_FAILED")
    x = np.array([[0.0], [1.0], [2.0]])
    solve = importlib.import_module("scipy.linalg").solve
    model = LinearRegression().fit(x, np.array([0.0, 2.0, 4.0]))
    if not np.allclose(model.predict([[3.0]]), [6.0]) or not np.allclose(solve(np.eye(2), np.ones(2)), np.ones(2)):
        raise ValueError("RUNTIME_SCIENTIFIC_LIBRARIES_FAILED")
    if not cv2.imencode(".png", np.zeros((8, 8), dtype=np.uint8))[0]:
        raise ValueError("RUNTIME_OPENCV_FAILED")
    if not socket.getaddrinfo("localhost", 0) or ssl.create_default_context().cert_store_stats()["x509_ca"] == 0:
        raise ValueError("RUNTIME_NETWORK_CONFIGURATION_FAILED")
    return {"native_features": "PASS", "minimal_runtime": not any(Path(p).exists() for p in ("/bin/sh", "/usr/bin/perl", "/usr/bin/apt", "/usr/bin/mount"))}


if __name__ == "__main__":
    print(json.dumps(run(Path("/data")) | features(Path("/data")), allow_nan=False))
