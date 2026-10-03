"""Compatibility facade for the decomposed safety interfaces."""

from __future__ import annotations

import math

import numpy as np

from .contracts import Policy, PositionPacket, SafetyAssessment, Vector3
from .safety_admittance import AdmittanceController as AdmittanceController


class HaloSafe:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.robot: PositionPacket | None = None
        self.human: PositionPacket | None = None
        self.latched = False

    def update(self, robot: PositionPacket, human: PositionPacket, now: float) -> None:
        for packet, old in ((robot, self.robot), (human, self.human)):
            if old is not None and packet.monotonic_seq <= old.monotonic_seq:
                self.latched = True
                raise ValueError("OBSERVATION_SEQUENCE_REJECTED")
            if not 0 <= now - packet.observed_at <= self.policy.max_observation_age_sec:
                self.latched = True
                raise ValueError("OBSERVATION_STALE")
            if packet.frame_id != "robot-base":
                self.latched = True
                raise ValueError("FRAME_MISMATCH")
        self.robot, self.human = robot, human

    def protective_distance(self, speed_mps: float) -> float:
        p = self.policy
        derived = p.human_approach_mps * (p.reaction_time_sec + p.stop_time_sec)
        derived += speed_mps * p.reaction_time_sec + p.braking_distance_m + p.uncertainty_m
        return max(p.min_separation_m, derived)

    def assess(self, target_mm: Vector3, speed_mps: float, now: float) -> SafetyAssessment:
        protective = self.protective_distance(speed_mps)
        reason, distance, scale = "SAFE", 0.0, 0.0
        if self.latched:
            reason = "STOP_LATCHED"
        elif self.robot is None or self.human is None:
            reason = "OBSERVATION_MISSING"
        elif not math.isfinite(now) or any(
            not 0 <= now - p.observed_at <= self.policy.max_observation_age_sec
            for p in (self.robot, self.human)
        ):
            reason = "OBSERVATION_STALE"
        elif not 0 < speed_mps <= self.policy.max_speed_mps:
            reason = "SPEED_NOT_ADMITTED"
        elif any(
            not math.isfinite(t) or not a <= t <= b
            for t, a, b in zip(
                target_mm, self.policy.workspace_min_mm, self.policy.workspace_max_mm
            )
        ):
            reason = "WORKSPACE_REJECTED"
        else:
            distance = self._path_distance(target_mm, self.robot, self.human)
            span = self.policy.full_speed_separation_m - protective
            scale = min(1.0, max(0.0, (distance - protective) / span)) if span > 0 else 0.0
            reason = "SAFE" if scale > 0 else "PROTECTIVE_STOP"
        return SafetyAssessment(
            admitted=scale > 0,
            scale_factor=scale,
            human_distance_m=distance,
            protective_distance_m=protective,
            rejection_reason=reason,
        )

    def _path_distance(self, target_mm: Vector3, robot: PositionPacket, human_packet: PositionPacket) -> float:
        """Closest distance to commanded straight segment, not just endpoint."""
        start = np.asarray(robot.position_mm, dtype=float)
        end, human = np.asarray(target_mm), np.asarray(human_packet.position_mm)
        direction = end - start
        norm = float(direction @ direction)
        t = float(np.clip((human - start) @ direction / norm, 0, 1)) if norm > 0 else 0.0
        return float(np.linalg.norm(human - (start + t * direction))) / 1000.0

    def reset(self, target_mm: Vector3, now: float) -> bool:
        self.latched = False
        assessment = self.assess(target_mm, self.policy.max_speed_mps, now)
        self.latched = not assessment.admitted
        return not self.latched
