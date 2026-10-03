"""REQ-DB-01/02, INV-02: durable intent precedes side effects, no silent write loss.

Historian design reuse from Sentinel; replaces swallowed failures and unbounded claims.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .ledger_errors import EvidenceError as EvidenceError
from .ledger_queries import recent, recover, task
from .ledger_replay import _verify_tasks, verify
from .ledger_transitions import _append, append, claim, transition


class Ledger:
    def __init__(self, path: Path, read_only: bool = False) -> None:
        self.path = path
        self.lock = threading.RLock()
        if read_only:
            self.db = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2, check_same_thread=False
            )
            if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise EvidenceError("DATABASE_SCHEMA_NOT_SUPPORTED")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
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
        CREATE INDEX IF NOT EXISTS packet_events ON events(packet_type,seq);
        CREATE TABLE IF NOT EXISTS tasks (
          request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
          state TEXT NOT NULL, rejection_reason TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS no_event_update BEFORE UPDATE ON events
          BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
        CREATE TRIGGER IF NOT EXISTS no_event_delete BEFORE DELETE ON events
          BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
        PRAGMA user_version=1;
        """)

    _append = _append

    append = append

    claim = claim

    transition = transition

    task = task

    recent = recent

    verify = verify

    _verify_tasks = _verify_tasks

    recover = recover

    def flush(self) -> None:
        with self.lock:
            result = self.db.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
            if result[0] != 0:
                raise EvidenceError("FLUSH_BUSY")

    def close(self) -> None:
        with self.lock:
            self.db.close()
