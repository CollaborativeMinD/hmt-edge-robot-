"""REQ-NF-01: strict, finite, frozen contracts; INV-01: no unchecked actuation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")]
Vector3 = tuple[Finite, Finite, Finite]


def canonical(value: Any) -> str:
    """Reject non-JSON and nonfinite values at persistence boundaries."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class Lane(StrEnum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"
    CONTINGENCY = "CONTINGENCY"
    EMERGENCY = "EMERGENCY"


class TaskState(StrEnum):
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Policy(Contract):
    policy_id: Identifier = "edge-v1"
    policy_epoch: int = Field(default=1, ge=1)
    workspace_min_mm: Vector3 = (-100.0, -100.0, 0.0)
    workspace_max_mm: Vector3 = (100.0, 100.0, 100.0)
    max_speed_mps: Positive = 0.25
    max_observation_age_sec: Positive = 0.5
    max_command_age_sec: Positive = 2.0
    session_timeout_sec: Positive = 300.0
    heartbeat_timeout_sec: Positive = 1.0
    verification_tolerance_mm: Positive = 0.1
    min_separation_m: Positive = 0.5
    full_speed_separation_m: Positive = 2.0
    reaction_time_sec: Nonnegative = 0.1
    stop_time_sec: Positive = 0.2
    braking_distance_m: Nonnegative = 0.05
    human_approach_mps: Nonnegative = 1.6
    uncertainty_m: Nonnegative = 0.05
    nominal_voltage_v: Positive = 3.7
    safe_voltage_v: Positive = 3.4
    max_temp_c: Positive = 85.0
    recovery_hysteresis_v: Positive = 0.05
    max_queue_size: int = Field(default=32, ge=1, le=1024)
    max_history_records: int = Field(default=256, ge=1, le=4096)
    driver_timeout_sec: Positive = 0.5
    allow_cloud: bool = False

    @model_validator(mode="after")
    def ordered_bounds(self) -> Policy:
        if any(a >= b for a, b in zip(self.workspace_min_mm, self.workspace_max_mm)):
            raise ValueError("WORKSPACE_BOUNDS_INVALID")
        if self.min_separation_m >= self.full_speed_separation_m:
            raise ValueError("SEPARATION_BOUNDS_INVALID")
        if self.safe_voltage_v >= self.nominal_voltage_v:
            raise ValueError("VOLTAGE_BOUNDS_INVALID")
        if self.heartbeat_timeout_sec > self.session_timeout_sec:
            raise ValueError("LEASE_BOUNDS_INVALID")
        return self


class PositionPacket(Contract):
    position_mm: Vector3
    frame_id: Identifier = "robot-base"
    monotonic_seq: int = Field(ge=0)
    observed_at: Nonnegative


class SensorSample(Contract):
    monotonic_seq: int = Field(ge=0)
    observed_at: Nonnegative
    voltage_v: Positive
    temp_c: Finite
    signal_dbm: Finite


class SensorAssessment(Contract):
    pace_lane: Lane
    poll_interval_sec: Positive
    data_valid: bool
    accepted_temp_c: Finite | None
    accepted_signal_dbm: Finite | None
    battery_margin: Annotated[float, Field(ge=0, le=1)]
    flush_required: bool
    rejection_reason: str


class SafetyAssessment(Contract):
    admitted: bool
    scale_factor: Annotated[float, Field(ge=0, le=1)]
    human_distance_m: Nonnegative
    protective_distance_m: Positive
    rejection_reason: str


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


class GraspObservation(Contract):
    target_mm: Vector3
    angle_deg: Finite
    primary_eigenvalue: Positive
    secondary_eigenvalue: Nonnegative
    ambiguity_ratio: Annotated[float, Field(ge=0, le=1)]
    calibration_id: Identifier
    frame_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResidentProposal(Contract):
    action: Literal["inspect", "diagnose", "plan_grasp", "hold"]
    explanation: str = Field(min_length=1, max_length=2048)
    evidence_refs: tuple[str, ...] = Field(max_length=32)


class ResidentReceipt(Contract):
    decision: Literal["ADMIT", "HOLD", "DENY"]
    proposal: ResidentProposal | None
    model_id: Identifier
    context_hash: str
    rejection_reason: str
    evidence_id: str
