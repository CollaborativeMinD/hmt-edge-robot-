"""contracts: policy interface."""

from __future__ import annotations

from pydantic import Field, model_validator

from .contracts_base import Contract, Identifier, Nonnegative, Positive, Vector3


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
