"""Ledger: transitions responsibilities on the owning instance."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from .contracts import TaskState, canonical, digest, utc_now
from .ledger_errors import EvidenceError

if TYPE_CHECKING:
    from hmt_edge_robot.ledger import Ledger

def _append(self: Ledger, producer: str, request_id: str, kind: str, payload: Any) -> str:
    row = self.db.execute(
        "SELECT seq,determinism_hash FROM events ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    seq, previous = (row[0] + 1, row[1]) if row else (1, "0" * 64)
    core = [seq, utc_now(), producer, request_id, kind, canonical(payload), previous]
    event_hash = digest(core)
    self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)", (*core, event_hash))
    return event_hash

def append(self: Ledger, producer: str, request_id: str, kind: str, payload: Any) -> str:
    try:
        with self.lock, self.db:
            return self._append(producer, request_id, kind, payload)
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc

def claim(self: Ledger, request_id: str, request_hash: str, payload: Any) -> str:
    try:
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?)", (request_id, request_hash, "PLANNED", "")
            )
            return self._append("orchestrator", request_id, "command_intent", payload)
    except sqlite3.IntegrityError as exc:
        raise EvidenceError("REQUEST_ALREADY_CLAIMED") from exc
    except sqlite3.Error as exc:
        raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc

def transition(self: Ledger, request_id: str, old: TaskState, new: TaskState, reason: str) -> str:
    allowed = {
        TaskState.PLANNED: {
            TaskState.EXECUTING,
            TaskState.DENIED,
            TaskState.CANCELLED,
            TaskState.FAILED,
        },
        TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED},
        TaskState.VERIFYING: {TaskState.SUCCEEDED, TaskState.FAILED},
    }
    if new not in allowed.get(old, set()):
        raise EvidenceError("TRANSITION_NOT_LAWFUL")
    try:
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cursor = self.db.execute(
                "UPDATE tasks SET state=?,rejection_reason=? WHERE request_id=? AND state=?",
                (new.value, reason, request_id, old.value),
            )
            if cursor.rowcount != 1:
                raise EvidenceError("TRANSITION_CONFLICT")
            return self._append(
                "orchestrator",
                request_id,
                "task_transition",
                {"state": new.value, "rejection_reason": reason},
            )
    except sqlite3.Error as exc:
        raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc
