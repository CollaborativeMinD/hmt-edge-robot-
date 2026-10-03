import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import request

from hmt_edge_robot.contracts import Policy, TaskState, digest
from hmt_edge_robot.ledger import EvidenceError, Ledger
from hmt_edge_robot.orchestrator import Feedback, SimulationDriver


def test_nominal_outcome_chain(cell, ready):
    assert cell.orchestrator.submit(request(cell, ready)).state == TaskState.PLANNED
    assert cell.orchestrator.run_next().state == TaskState.SUCCEEDED
    assert cell.driver.moves == 1 and cell.driver.held
    assert cell.ledger.task("task-1")["state"] == "SUCCEEDED"
    assert cell.orchestrator.run_next() is None
    assert cell.ledger.verify() == 7


class FailedDriver(SimulationDriver):
    def move_to(self, target_mm, speed_mps, timeout_sec):
        return False


class FailedGripper(SimulationDriver):
    def gripper_close(self, timeout_sec):
        return False


class BadFeedback(SimulationDriver):
    def feedback(self, timeout_sec):
        return Feedback((99.0, 0.0, 0.0), True)


class EmptyGrasp(SimulationDriver):
    def feedback(self, timeout_sec):
        return Feedback(self.position, False)


class NonfiniteFeedback(SimulationDriver):
    def feedback(self, timeout_sec):
        return Feedback((float("nan"), 0.0, 0.0), True)


@pytest.mark.parametrize(
    "driver,reason",
    [
        (FailedDriver, "MOVE_ACK_REJECTED"),
        (FailedGripper, "GRIPPER_ACK_REJECTED"),
        (BadFeedback, "POSITION_NOT_CONFIRMED"),
        (EmptyGrasp, "GRASP_NOT_CONFIRMED"),
        (NonfiniteFeedback, "FEEDBACK_INVALID"),
    ],
)
def test_driver_ack_and_feedback_regressions(cell, ready, driver, reason):
    cell.orchestrator.driver = driver()
    cell.orchestrator.submit(request(cell, ready))
    result = cell.orchestrator.run_next()
    assert result.state == TaskState.FAILED and result.rejection_reason == reason
    assert cell.orchestrator.stopped and cell.safety.latched
    assert cell.orchestrator.fault_count == 1
    assert cell.orchestrator.driver.stopped
    assert cell.ledger.task("task-1")["state"] == "FAILED"


@pytest.mark.parametrize(
    "changes,reason",
    [
        (dict(policy_epoch=2), "POLICY_EPOCH_MISMATCH"),
        (dict(session_id="ghost"), "AUTHORITY_NOT_ADMITTED"),
        (dict(target_mm=(1000.0, 0.0, 0.0)), "WORKSPACE_REJECTED"),
        (dict(issued_at=5.0, expires_at=6.0), "COMMAND_EXPIRED"),
    ],
)
def test_admission_denials(cell, ready, changes, reason):
    result = cell.orchestrator.submit(request(cell, ready, **changes))
    assert result.state == TaskState.DENIED and result.rejection_reason == reason
    assert cell.driver.moves == 0


def test_substrate_stop_and_pending_revalidation(cell, ready, clock):
    cell.orchestrator.submit(request(cell, ready))
    clock.now = 10.6
    assert cell.orchestrator.run_next().rejection_reason == "SUBSTRATE_NOT_READY"
    cell.observe_simulation(1)
    cell.orchestrator.submit(request(cell, ready, "fresh"))
    cell.orchestrator.stop()
    assert cell.orchestrator.run_next().rejection_reason == "STOP_LATCHED"
    assert cell.driver.moves == 0
    assert cell.orchestrator.reset(ready, "operator")
    assert not cell.orchestrator.reset("ghost", "operator")
    cell.edge.halted = True
    assert not cell.orchestrator.reset(ready, "operator")


def test_queue_backpressure_and_cancel(cell, ready):
    cell.orchestrator.policy = Policy(max_queue_size=1)
    cell.orchestrator.submit(request(cell, ready))
    assert (
        cell.orchestrator.submit(request(cell, ready, "overflow")).rejection_reason
        == "QUEUE_CAPACITY_EXHAUSTED"
    )
    with pytest.raises(PermissionError):
        cell.orchestrator.cancel("task-1", "ghost", "operator")
    assert cell.orchestrator.cancel("task-1", ready, "operator").state == TaskState.CANCELLED
    with pytest.raises(ValueError):
        cell.orchestrator.cancel("task-1", ready, "operator")
    assert not cell.orchestrator.queue


def test_duplicate_atomic_admission(cell, ready):
    order = request(cell, ready)

    def submit():
        try:
            return cell.orchestrator.submit(order).state
        except EvidenceError:
            return "DUPLICATE"

    with ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(lambda _: submit(), range(4)))
    assert states.count(TaskState.PLANNED) == 1
    assert states.count("DUPLICATE") == 3
    assert len(cell.orchestrator.queue) == 1
    cell.orchestrator.run_next()
    assert cell.driver.moves == 1


def test_authority_rechecked_after_movement(cell, ready):
    class RevokeDriver(SimulationDriver):
        def move_to(self, target_mm, speed_mps, timeout_sec):
            ack = super().move_to(target_mm, speed_mps, timeout_sec)
            cell.access.revoke(ready)
            return ack

    driver = RevokeDriver()
    cell.orchestrator.driver = driver
    cell.orchestrator.submit(request(cell, ready))
    result = cell.orchestrator.run_next()
    assert result.state == TaskState.FAILED
    assert not driver.held


def test_deadline_detection_and_stop(cell, ready, clock):
    class SlowDriver(SimulationDriver):
        def move_to(self, target_mm, speed_mps, timeout_sec):
            clock.now += timeout_sec + 0.01
            return True

    cell.orchestrator.driver = SlowDriver()
    cell.orchestrator.submit(request(cell, ready))
    result = cell.orchestrator.run_next()
    assert result.rejection_reason == "DRIVER_DEADLINE_EXCEEDED"
    assert cell.orchestrator.stopped


def test_evidence_failure_stops_before_side_effect(cell, ready, monkeypatch):
    cell.orchestrator.submit(request(cell, ready))

    def fail(*args):
        raise EvidenceError("EVIDENCE_WRITE_FAILED")

    monkeypatch.setattr(cell.ledger, "transition", fail)
    with pytest.raises(EvidenceError):
        cell.orchestrator.run_next()
    assert cell.driver.moves == 0 and cell.driver.stopped


def test_policy_update_revokes_pending_authority(cell, ready):
    cell.orchestrator.submit(request(cell, ready))
    with pytest.raises(PermissionError):
        cell.update_policy(Policy(policy_epoch=2), "ghost", "operator")
    with pytest.raises(ValueError):
        cell.update_policy(Policy(), ready, "operator")
    cell.update_policy(Policy(policy_epoch=2), ready, "operator")
    assert not cell.access.sessions
    assert cell.orchestrator.run_next().rejection_reason == "POLICY_EPOCH_MISMATCH"
    assert cell.driver.moves == 0


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
