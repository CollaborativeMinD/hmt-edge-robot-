"""Ledger: replay responsibilities on the owning instance."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .contracts import digest
from .ledger_errors import EvidenceError

if TYPE_CHECKING:
    from hmt_edge_robot.ledger import Ledger

def verify(self: Ledger) -> int:
    previous, count = "0" * 64, 0
    with self.lock:
        cursor = self.db.execute("SELECT * FROM events ORDER BY seq")
        for row in cursor:
            if row[0] != count + 1 or row[6] != previous or digest(list(row[:7])) != row[7]:
                raise EvidenceError("REPLAY_HASH_MISMATCH")
            previous, count = row[7], count + 1
        self._verify_tasks()
    return count

def _verify_tasks(self: Ledger) -> None:
    for request_id, request_hash, state, reason in self.db.execute("SELECT * FROM tasks"):
        intent = self.db.execute(
            "SELECT payload FROM events WHERE request_id=? AND packet_type='command_intent' ORDER BY seq LIMIT 1",
            (request_id,),
        ).fetchone()
        transition = self.db.execute(
            "SELECT payload FROM events WHERE request_id=? AND packet_type='task_transition' ORDER BY seq DESC LIMIT 1",
            (request_id,),
        ).fetchone()
        expected = (
            json.loads(transition[0])
            if transition
            else {"state": "PLANNED", "rejection_reason": ""}
        )
        if (
            intent is None
            or digest(json.loads(intent[0])) != request_hash
            or state != expected["state"]
            or reason != expected["rejection_reason"]
        ):
            raise EvidenceError("TASK_PROJECTION_MISMATCH")
