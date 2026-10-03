"""Ledger: queries responsibilities on the owning instance."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .contracts import TaskState

if TYPE_CHECKING:
    from hmt_edge_robot.ledger import Ledger

def task(self: Ledger, request_id: str) -> dict[str, str] | None:
    with self.lock:
        row = self.db.execute(
            "SELECT state,rejection_reason FROM tasks WHERE request_id=?", (request_id,)
        ).fetchone()
    return None if row is None else {"state": row[0], "rejection_reason": row[1]}

def recent(self: Ledger, limit: int = 32) -> list[dict[str, Any]]:
    if type(limit) is not int or not 1 <= limit <= 4096:
        raise ValueError("QUERY_LIMIT_INVALID")
    with self.lock:
        rows = self.db.execute(
            "SELECT * FROM events ORDER BY seq DESC LIMIT ?", (limit,)
        ).fetchall()
    keys = (
        "monotonic_seq",
        "timestamp_utc",
        "producer_id",
        "request_id",
        "packet_type",
        "payload",
        "previous_hash",
        "determinism_hash",
    )
    return [dict(zip(keys, (*r[:5], json.loads(r[5]), *r[6:]))) for r in reversed(rows)]

def recover(self: Ledger) -> int:
    """Unfinished commands are uncertain after restart; never auto-execute."""
    with self.lock:
        rows = self.db.execute(
            "SELECT request_id,state FROM tasks WHERE state IN ('PLANNED','EXECUTING','VERIFYING')"
        ).fetchall()
    for request_id, state in rows:
        self.transition(
            request_id, TaskState(state), TaskState.FAILED, "RESTART_RECONCILIATION_REQUIRED"
        )
    return len(rows)
