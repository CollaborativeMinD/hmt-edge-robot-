"""FactoryOrchestrator: execution responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import MotionRequest, TaskReceipt, TaskState
from .ledger import EvidenceError
from .orchestrator_driver import Driver as Driver
from .orchestrator_driver import Feedback as Feedback
from .orchestrator_driver import SimulationDriver as SimulationDriver

if TYPE_CHECKING:
    from hmt_edge_robot.orchestrator import FactoryOrchestrator

def run_next(self: FactoryOrchestrator) -> TaskReceipt | None:
    with self.lock:
        if not self.queue:
            return None
        request = self.queue.popleft()
        state = TaskState.PLANNED
        try:
            reason = self._guard(request)
            if reason != "ADMITTED":
                evidence = self.ledger.transition(
                    request.request_id, state, TaskState.DENIED, reason
                )
                return self._receipt(request.request_id, TaskState.DENIED, reason, evidence)
            self.ledger.transition(
                request.request_id, state, TaskState.EXECUTING, "EXECUTION_ADMITTED"
            )
            state = TaskState.EXECUTING
            self._execute(request)
            self.ledger.transition(
                request.request_id, state, TaskState.VERIFYING, "DRIVER_ACKNOWLEDGED"
            )
            state = TaskState.VERIFYING
            self._verify(request)
            evidence = self.ledger.transition(
                request.request_id, state, TaskState.SUCCEEDED, "OUTCOME_VERIFIED"
            )
            self.fault_count = 0
            return self._receipt(
                request.request_id, TaskState.SUCCEEDED, "OUTCOME_VERIFIED", evidence
            )
        except EvidenceError:
            self.stop()
            raise
        except (RuntimeError, ValueError, TimeoutError, OSError) as exc:
            self.fault_count += 1
            self.stop()
            evidence = self.ledger.transition(
                request.request_id, state, TaskState.FAILED, str(exc)
            )
            return self._receipt(request.request_id, TaskState.FAILED, str(exc), evidence)

def _execute(self: FactoryOrchestrator, request: MotionRequest) -> None:
    reason = self._guard(request)
    if reason != "ADMITTED":
        raise RuntimeError(reason)
    scale = self.safety.assess(request.target_mm, request.speed_mps, self.clock()).scale_factor
    start = self.clock()
    ack = self.driver.move_to(
        request.target_mm, request.speed_mps * scale, self.policy.driver_timeout_sec
    )
    if ack is not True:
        raise RuntimeError("MOVE_ACK_REJECTED")
    self._deadline(start)
    reason = self._guard(request)
    if reason != "ADMITTED":
        raise RuntimeError(reason)
    start = self.clock()
    if self.driver.gripper_close(self.policy.driver_timeout_sec) is not True:
        raise RuntimeError("GRIPPER_ACK_REJECTED")
    self._deadline(start)

def _verify(self: FactoryOrchestrator, request: MotionRequest) -> None:
    start = self.clock()
    feedback = self.driver.feedback(self.policy.driver_timeout_sec)
    self._deadline(start)
    if self._guard(request) != "ADMITTED":
        raise RuntimeError("VERIFICATION_AUTHORITY_EXPIRED")
    if not isinstance(feedback, Feedback) or feedback.object_held is not True:
        raise RuntimeError("GRASP_NOT_CONFIRMED")
    from math import isfinite

    if len(feedback.position_mm) != 3 or not all(isfinite(x) for x in feedback.position_mm):
        raise RuntimeError("FEEDBACK_INVALID")
    if any(
        abs(a - b) > self.policy.verification_tolerance_mm
        for a, b in zip(feedback.position_mm, request.target_mm)
    ):
        raise RuntimeError("POSITION_NOT_CONFIRMED")
