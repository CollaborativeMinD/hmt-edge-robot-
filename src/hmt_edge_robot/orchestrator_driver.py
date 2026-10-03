"""orchestrator: driver interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .contracts import Vector3


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
