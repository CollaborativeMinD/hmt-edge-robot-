"""contracts: motion interface."""

from __future__ import annotations

from pydantic import Field, model_validator

from .contracts_base import Contract, Identifier, Lane, Nonnegative, Positive, TaskState, Vector3


class MotionRequest(Contract):
    request_id: Identifier
    operator_id: Identifier
    session_id: Identifier
    policy_epoch: int = Field(ge=1)
    target_mm: Vector3
    speed_mps: Positive
    issued_at: Nonnegative
    expires_at: Nonnegative

    @model_validator(mode="after")
    def valid_interval(self) -> MotionRequest:
        if self.expires_at <= self.issued_at:
            raise ValueError("COMMAND_INTERVAL_INVALID")
        return self

class TaskReceipt(Contract):
    request_id: Identifier
    state: TaskState
    pace_lane: Lane
    rejection_reason: str
    evidence_id: str
