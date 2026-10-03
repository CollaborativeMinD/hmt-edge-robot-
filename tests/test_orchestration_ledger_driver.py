"""test_orchestration_ledger: driver interface."""



import pytest
from conftest import request

from hmt_edge_robot.contracts import TaskState
from hmt_edge_robot.orchestrator import Feedback, SimulationDriver


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
