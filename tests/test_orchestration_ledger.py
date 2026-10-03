"""Compatibility facade for the decomposed test_orchestration_ledger interfaces."""



import pytest
from conftest import request
from test_orchestration_ledger_driver import BadFeedback as BadFeedback
from test_orchestration_ledger_driver import EmptyGrasp as EmptyGrasp
from test_orchestration_ledger_driver import FailedDriver as FailedDriver
from test_orchestration_ledger_driver import FailedGripper as FailedGripper
from test_orchestration_ledger_driver import NonfiniteFeedback as NonfiniteFeedback

from hmt_edge_robot.contracts import Policy, TaskState


def test_nominal_outcome_chain(cell, ready):
    assert cell.orchestrator.submit(request(cell, ready)).state == TaskState.PLANNED
    assert cell.orchestrator.run_next().state == TaskState.SUCCEEDED
    assert cell.driver.moves == 1 and cell.driver.held
    assert cell.ledger.task("task-1")["state"] == "SUCCEEDED"
    assert cell.orchestrator.run_next() is None
    assert cell.ledger.verify() == 7

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
