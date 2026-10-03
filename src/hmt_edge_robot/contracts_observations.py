"""contracts: observations interface."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .contracts_base import Contract, Finite, Identifier, Lane, Nonnegative, Positive, Vector3


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
