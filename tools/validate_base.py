"""Shared validate primitives and declarations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from hmt_edge_robot.contracts import utc_now

ROOT = Path(__file__).resolve().parents[1]

EVIDENCE = ROOT / "evidence"

RUN = EVIDENCE / "runs" / utc_now().replace(":", "-")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
