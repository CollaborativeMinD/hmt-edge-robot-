"""FactoryOrchestrator: admission responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import Lane, MotionRequest, TaskReceipt, TaskState, digest
from .orchestrator_driver import Driver as Driver
from .orchestrator_driver import Feedback as Feedback
from .orchestrator_driver import SimulationDriver as SimulationDriver

if TYPE_CHECKING:
    from hmt_edge_robot.orchestrator import FactoryOrchestrator

def _guard(self: FactoryOrchestrator, request: MotionRequest) -> str:
    now = self.clock()
    if self.stopped or self.safety.latched:
        return "STOP_LATCHED"
    if request.policy_epoch != self.policy.policy_epoch:
        return "POLICY_EPOCH_MISMATCH"
    if (
        not 0 <= now - request.issued_at <= self.policy.max_command_age_sec
        or now >= request.expires_at
    ):
        return "COMMAND_EXPIRED"
    if not self.access.authorize(request.session_id, request.operator_id, "motion", now):
        return "AUTHORITY_NOT_ADMITTED"
    if self.edge.halted or not self.edge.history:
        return "SUBSTRATE_NOT_READY"
    if (
        not self.edge.history[-1].data_valid
        or now - self.edge.last_time > self.policy.max_observation_age_sec
    ):
        return "SUBSTRATE_NOT_READY"
    assessment = self.safety.assess(request.target_mm, request.speed_mps, now)
    return "ADMITTED" if assessment.admitted else assessment.rejection_reason

def _receipt(
    self: FactoryOrchestrator, request_id: str, state: TaskState, reason: str, evidence: str
) -> TaskReceipt:
    lane = (
        Lane.EMERGENCY
        if self.stopped
        else Lane.ALTERNATE
        if state != TaskState.SUCCEEDED
        else Lane.PRIMARY
    )
    return TaskReceipt(
        request_id=request_id,
        state=state,
        pace_lane=lane,
        rejection_reason=reason,
        evidence_id=evidence,
    )

def submit(self: FactoryOrchestrator, request: MotionRequest) -> TaskReceipt:
    with self.lock:
        payload = request.model_dump(mode="json")
        evidence = self.ledger.claim(request.request_id, digest(payload), payload)
        reason = self._guard(request)
        if len(self.queue) >= self.policy.max_queue_size:
            reason = "QUEUE_CAPACITY_EXHAUSTED"
        if reason != "ADMITTED":
            evidence = self.ledger.transition(
                request.request_id, TaskState.PLANNED, TaskState.DENIED, reason
            )
            return self._receipt(request.request_id, TaskState.DENIED, reason, evidence)
        self.queue.append(request)
        return self._receipt(request.request_id, TaskState.PLANNED, reason, evidence)

def cancel(self: FactoryOrchestrator, request_id: str, session_id: str, operator_id: str) -> TaskReceipt:
    with self.lock:
        if not self.access.authorize(session_id, operator_id, "motion", self.clock()):
            raise PermissionError("AUTHORITY_NOT_ADMITTED")
        request = next(
            (
                r
                for r in self.queue
                if r.request_id == request_id and r.operator_id == operator_id
            ),
            None,
        )
        if request is None:
            raise ValueError("TASK_NOT_CANCELLABLE")
        evidence = self.ledger.transition(
            request_id, TaskState.PLANNED, TaskState.CANCELLED, "OPERATOR_CANCELLED"
        )
        self.queue.remove(request)
        return self._receipt(request_id, TaskState.CANCELLED, "OPERATOR_CANCELLED", evidence)
