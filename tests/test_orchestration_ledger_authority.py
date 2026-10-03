"""test_orchestration_ledger: authority interface."""


from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import request

from hmt_edge_robot.contracts import Policy, TaskState
from hmt_edge_robot.ledger import EvidenceError
from hmt_edge_robot.orchestrator import SimulationDriver


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
