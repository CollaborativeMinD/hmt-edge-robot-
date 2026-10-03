"""safety: admittance interface."""

from __future__ import annotations

import math

import numpy as np

from .contracts import Vector3


class AdmittanceController:
    """SIL only: M*a+D*v+K*x=F; FF-V6-DYN-01, FF-V6-DISC-01."""

    def __init__(
        self, mass: float = 5.0, damping: float = 10.0, stiffness: float = 0.0, dt: float = 0.01
    ) -> None:
        if not all(math.isfinite(x) for x in (mass, damping, stiffness, dt)):
            raise ValueError("PHYSICS_NONFINITE")
        if mass <= 0 or damping < 0 or stiffness < 0 or not 0 < dt <= 0.05:
            raise ValueError("PHYSICS_BOUNDS_INVALID")
        self.mass, self.damping, self.stiffness, self.dt = mass, damping, stiffness, dt
        self.position, self.velocity = np.zeros(3), np.zeros(3)

    def step(self, force: Vector3) -> tuple[Vector3, Vector3]:
        if len(force) != 3 or not all(math.isfinite(x) for x in force):
            raise ValueError("FORCE_INVALID")
        acceleration = (
            np.asarray(force) - self.damping * self.velocity - self.stiffness * self.position
        ) / self.mass
        velocity = self.velocity + acceleration * self.dt
        position = self.position + velocity * self.dt
        if not np.isfinite(position).all() or not np.isfinite(velocity).all():
            raise ValueError("PHYSICS_UPDATE_NONFINITE")
        self.position, self.velocity = position, velocity
        return ((float(position[0]), float(position[1]), float(position[2])),
                (float(velocity[0]), float(velocity[1]), float(velocity[2])))
