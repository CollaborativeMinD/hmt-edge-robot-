"""REQ-WEN-01..03: bounded history, hysteresis, immutable gaps, durable halt intent.

Adapted from WaialuaEdgeNodeLambda classify/process; no silent pandas fallback.
"""

from __future__ import annotations

import math
from collections import deque

from .contracts import Lane, Policy, SensorAssessment, SensorSample
from .ledger import Ledger


class WaialuaEdgeNode:
    def __init__(self, policy: Policy, ledger: Ledger) -> None:
        self.policy, self.ledger = policy, ledger
        self.history: deque[SensorAssessment] = deque(maxlen=policy.max_history_records)
        self.last_seq, self.last_time = -1, -1.0
        self.power_lane = Lane.PRIMARY
        self.halted = False

    def process(self, sample: SensorSample, now: float) -> SensorAssessment:
        if self.halted:
            raise RuntimeError("NODE_HALTED")
        if sample.monotonic_seq <= self.last_seq or sample.observed_at < self.last_time:
            raise ValueError("SENSOR_SEQUENCE_REJECTED")
        if (
            not math.isfinite(now)
            or not 0 <= now - sample.observed_at <= self.policy.max_observation_age_sec
        ):
            raise ValueError("SENSOR_STALE")
        lane = self._classify(sample.voltage_v)
        thermal = sample.temp_c > self.policy.max_temp_c
        valid = not thermal and lane != Lane.EMERGENCY
        display_lane = Lane.CONTINGENCY if thermal and lane != Lane.EMERGENCY else lane
        reason = (
            "POWER_CRITICAL" if lane == Lane.EMERGENCY else "THERMAL_GAP" if thermal else "VALID"
        )
        margin = (sample.voltage_v - self.policy.safe_voltage_v) / (
            self.policy.nominal_voltage_v - self.policy.safe_voltage_v
        )
        result = SensorAssessment(
            pace_lane=display_lane,
            poll_interval_sec=5.0 if lane == Lane.ALTERNATE else 1.0,
            data_valid=valid,
            accepted_temp_c=sample.temp_c if valid else None,
            accepted_signal_dbm=sample.signal_dbm if valid else None,
            battery_margin=min(1.0, max(0.0, margin)),
            flush_required=lane == Lane.EMERGENCY,
            rejection_reason=reason,
        )
        self.ledger.append(
            "edge",
            str(sample.monotonic_seq),
            "sensor_assessment",
            {
                "sample": sample.model_dump(mode="json"),
                "assessment": result.model_dump(mode="json"),
            },
        )
        self.power_lane, self.last_seq, self.last_time = (
            lane,
            sample.monotonic_seq,
            sample.observed_at,
        )
        self.history.append(result)
        if lane == Lane.EMERGENCY:
            self.halted = True
            self.ledger.flush()
        return result

    def _classify(self, voltage: float) -> Lane:
        if voltage <= self.policy.safe_voltage_v:
            return Lane.EMERGENCY
        recovery = self.policy.nominal_voltage_v + self.policy.recovery_hysteresis_v
        if voltage <= self.policy.nominal_voltage_v or (
            self.power_lane == Lane.ALTERNATE and voltage < recovery
        ):
            return Lane.ALTERNATE
        return Lane.PRIMARY
