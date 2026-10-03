"""test_orchestration_ledger: replay interface."""

import sqlite3

import pytest

from hmt_edge_robot.contracts import TaskState, digest
from hmt_edge_robot.ledger import EvidenceError, Ledger


def test_ledger_restart_append_only_and_law(tmp_path):
    path = tmp_path / "evidence.db"
    ledger = Ledger(path)
    ledger.claim("unfinished", digest({"command": 1}), {"command": 1})
    ledger.close()
    reopened = Ledger(path)
    assert reopened.recover() == 1
    task = reopened.task("unfinished")
    assert task is not None
    assert task["state"] == "FAILED"
    assert reopened.verify() == 2
    with pytest.raises(EvidenceError):
        reopened.transition("unfinished", TaskState.FAILED, TaskState.SUCCEEDED, "invented")
    with pytest.raises(EvidenceError):
        reopened.transition("missing", TaskState.PLANNED, TaskState.EXECUTING, "invented")
    with pytest.raises(sqlite3.IntegrityError):
        reopened.db.execute("UPDATE events SET producer_id='tamper'")
    with pytest.raises(sqlite3.IntegrityError):
        reopened.db.execute("DELETE FROM events")
    reopened.close()

def test_ledger_corruption_detected(cell):
    cell.ledger.append("test", "1", "event", {"value": 1})
    cell.ledger.db.execute("DROP TRIGGER no_event_update")
    cell.ledger.db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(EvidenceError):
        cell.ledger.verify()

def test_ledger_errors_and_bounds(tmp_path):
    ledger = Ledger(tmp_path / "db")
    for limit in (0, 5000, True):
        with pytest.raises(ValueError):
            ledger.recent(limit)
    ledger.close()
    with pytest.raises(EvidenceError):
        ledger.append("test", "1", "event", {})
    with pytest.raises(EvidenceError):
        ledger.claim("1", "hash", {})
    with pytest.raises(EvidenceError):
        ledger.transition("1", TaskState.PLANNED, TaskState.EXECUTING, "test")
