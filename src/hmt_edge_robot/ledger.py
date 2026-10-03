"""REQ-DB-01/02, INV-02: durable intent precedes side effects, no silent write loss.

Historian design reuse from Sentinel; replaces swallowed failures and unbounded claims.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .contracts import TaskState, canonical, digest, utc_now


class EvidenceError(RuntimeError):
    """Persistence or replay integrity failed; caller must stop admission."""


class Ledger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=2, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY, timestamp_utc TEXT NOT NULL,
          producer_id TEXT NOT NULL, request_id TEXT NOT NULL,
          packet_type TEXT NOT NULL, payload TEXT NOT NULL,
          previous_hash TEXT NOT NULL, determinism_hash TEXT NOT NULL UNIQUE);
        CREATE INDEX IF NOT EXISTS request_events ON events(request_id,seq);
        CREATE TABLE IF NOT EXISTS tasks (
          request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
          state TEXT NOT NULL, rejection_reason TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS no_event_update BEFORE UPDATE ON events
          BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
        CREATE TRIGGER IF NOT EXISTS no_event_delete BEFORE DELETE ON events
          BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
        PRAGMA user_version=1;
        """)

    def _append(self, producer: str, request_id: str, kind: str, payload: Any) -> str:
        row = self.db.execute("SELECT seq,determinism_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (row[0] + 1, row[1]) if row else (1, "0" * 64)
        core = [seq, utc_now(), producer, request_id, kind, canonical(payload), previous]
        event_hash = digest(core)
        self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)", (*core, event_hash))
        return event_hash

    def append(self, producer: str, request_id: str, kind: str, payload: Any) -> str:
        try:
            with self.lock, self.db:
                return self._append(producer, request_id, kind, payload)
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc

    def claim(self, request_id: str, request_hash: str, payload: Any) -> str:
        try:
            with self.lock, self.db:
                self.db.execute("BEGIN IMMEDIATE")
                self.db.execute("INSERT INTO tasks VALUES(?,?,?,?)", (request_id, request_hash, "PLANNED", ""))
                return self._append("orchestrator", request_id, "command_intent", payload)
        except sqlite3.IntegrityError as exc:
            raise EvidenceError("REQUEST_ALREADY_CLAIMED") from exc
        except sqlite3.Error as exc:
            raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc

    def transition(self, request_id: str, old: TaskState, new: TaskState, reason: str) -> str:
        allowed = {TaskState.PLANNED: {TaskState.EXECUTING, TaskState.DENIED, TaskState.CANCELLED, TaskState.FAILED},
                   TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED},
                   TaskState.VERIFYING: {TaskState.SUCCEEDED, TaskState.FAILED}}
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
                return self._append("orchestrator", request_id, "task_transition", {"state": new.value, "rejection_reason": reason})
        except sqlite3.Error as exc:
            raise EvidenceError("EVIDENCE_WRITE_FAILED") from exc

    def task(self, request_id: str) -> dict[str, str] | None:
        with self.lock:
            row = self.db.execute("SELECT state,rejection_reason FROM tasks WHERE request_id=?", (request_id,)).fetchone()
        return None if row is None else {"state": row[0], "rejection_reason": row[1]}

    def recent(self, limit: int = 32) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError("QUERY_LIMIT_INVALID")
        with self.lock:
            rows = self.db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        keys = ("monotonic_seq", "timestamp_utc", "producer_id", "request_id", "packet_type", "payload", "previous_hash", "determinism_hash")
        return [dict(zip(keys, (*r[:5], json.loads(r[5]), *r[6:]))) for r in reversed(rows)]

    def verify(self) -> int:
        previous, count = "0" * 64, 0
        with self.lock:
            cursor = self.db.execute("SELECT * FROM events ORDER BY seq")
            for row in cursor:
                if row[0] != count + 1 or row[6] != previous or digest(list(row[:7])) != row[7]:
                    raise EvidenceError("REPLAY_HASH_MISMATCH")
                previous, count = row[7], count + 1
        return count

    def recover(self) -> int:
        """Unfinished commands are uncertain after restart; never auto-execute."""
        with self.lock:
            rows = self.db.execute("SELECT request_id,state FROM tasks WHERE state IN ('PLANNED','EXECUTING','VERIFYING')").fetchall()
        for request_id, state in rows:
            self.transition(request_id, TaskState(state), TaskState.FAILED, "RESTART_RECONCILIATION_REQUIRED")
        return len(rows)

    def flush(self) -> None:
        with self.lock:
            result = self.db.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
            if result[0] != 0:
                raise EvidenceError("FLUSH_BUSY")

    def close(self) -> None:
        with self.lock:
            self.db.close()
