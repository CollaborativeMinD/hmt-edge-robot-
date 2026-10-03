"""FactoryOrchestrator: recovery responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .orchestrator_driver import Driver as Driver
from .orchestrator_driver import Feedback as Feedback
from .orchestrator_driver import SimulationDriver as SimulationDriver

if TYPE_CHECKING:
    from hmt_edge_robot.orchestrator import FactoryOrchestrator

def _deadline(self: FactoryOrchestrator, started: float) -> None:
    if not 0 <= self.clock() - started <= self.policy.driver_timeout_sec:
        raise TimeoutError("DRIVER_DEADLINE_EXCEEDED")

def stop(self: FactoryOrchestrator) -> None:
    self.stopped, self.safety.latched = True, True
    self.driver.emergency_stop()

def reset(self: FactoryOrchestrator, session_id: str, operator_id: str) -> bool:
    with self.lock:
        if not self.access.authorize(session_id, operator_id, "reset", self.clock()):
            return False
        # Physical reset must be a separately qualified adapter operation.
        if not isinstance(self.driver, SimulationDriver):
            return False
        if not self.edge.history or self.edge.halted or not self.edge.history[-1].data_valid:
            return False
        if not self.safety.reset(self.driver.position, self.clock()):
            return False
        self.ledger.append(
            "orchestrator",
            operator_id,
            "stop_reset",
            {"policy_epoch": self.policy.policy_epoch},
        )
        self.stopped, self.driver.stopped = False, False
        return True
