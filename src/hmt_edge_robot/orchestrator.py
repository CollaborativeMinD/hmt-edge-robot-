"""REQ-FO-01..04, INV-01..04: guarded command lifecycle, feedback-bound success.

FactoryOrchestratorLambda's adapter separation and PACE semantics retained.
No retreat/reboot motion is authorized merely because a fault occurred.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Protocol

from .access import AccessManager
from .contracts import Lane, MotionRequest, Policy, TaskReceipt, TaskState, Vector3, digest
from .edge import WaialuaEdgeNode
from .ledger import EvidenceError, Ledger
from .safety import HaloSafe


@dataclass(frozen=True)
class Feedback:
    position_mm: Vector3
    object_held: bool


class Driver(Protocol):
    """Physical adapters must independently enforce timeout and stop guarantees."""

    def move_to(self, target_mm: Vector3, speed_mps: float, timeout_sec: float) -> bool: ...
    def gripper_close(self, timeout_sec: float) -> bool: ...
    def feedback(self, timeout_sec: float) -> Feedback: ...
    def emergency_stop(self) -> None: ...


class SimulationDriver:
    def __init__(self) -> None:
        self.position: Vector3 = (0.0, 0.0, 0.0)
        self.held, self.stopped, self.moves = False, False, 0

    def move_to(self, target_mm: Vector3, speed_mps: float, timeout_sec: float) -> bool:
        if self.stopped:
            return False
        self.position, self.moves = target_mm, self.moves + 1
        return True

    def gripper_close(self, timeout_sec: float) -> bool:
        self.held = not self.stopped
        return self.held

    def feedback(self, timeout_sec: float) -> Feedback:
        return Feedback(self.position, self.held)

    def emergency_stop(self) -> None:
        self.stopped = True


class FactoryOrchestrator:
    def __init__(
        self,
        policy: Policy,
        ledger: Ledger,
        access: AccessManager,
        safety: HaloSafe,
        edge: WaialuaEdgeNode,
        driver: Driver,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy, self.ledger, self.access = policy, ledger, access
        self.safety, self.edge, self.driver, self.clock = safety, edge, driver, clock
        self.lock = threading.RLock()
        self.queue: deque[MotionRequest] = deque()
        self.fault_count, self.stopped = 0, False

    def _guard(self, request: MotionRequest) -> str:
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
        self, request_id: str, state: TaskState, reason: str, evidence: str
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

    def submit(self, request: MotionRequest) -> TaskReceipt:
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

    def cancel(self, request_id: str, session_id: str, operator_id: str) -> TaskReceipt:
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

    def run_next(self) -> TaskReceipt | None:
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

    def _execute(self, request: MotionRequest) -> None:
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

    def _verify(self, request: MotionRequest) -> None:
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

    def _deadline(self, started: float) -> None:
        if not 0 <= self.clock() - started <= self.policy.driver_timeout_sec:
            raise TimeoutError("DRIVER_DEADLINE_EXCEEDED")

    def stop(self) -> None:
        self.stopped, self.safety.latched = True, True
        self.driver.emergency_stop()

    def reset(self, session_id: str, operator_id: str) -> bool:
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
