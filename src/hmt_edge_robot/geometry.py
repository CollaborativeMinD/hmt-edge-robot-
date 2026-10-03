"""REQ-NG-02: fixed 16-coefficient PGA, adapted from the supplied GA field card.

FF-GA-01/GA-EQ-01..04; FF-PGA-01/PGA-EQ-01..08: M P reverse(M).
Fixed algebra size bounds computation; Python is a supervisory/SIL partition.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from .contracts import Contract, Finite, Identifier, Positive, Vector3

Array = NDArray[np.float64]


def gp(a: Array, b: Array) -> Array:
    out = np.zeros(16)
    for am in range(16):
        for bm in range(16):
            if am & bm & 1:
                continue
            flips = sum((bm & ((1 << i) - 1)).bit_count() for i in range(4) if am & (1 << i))
            out[am ^ bm] += a[am] * b[bm] * (-1.0 if flips % 2 else 1.0)
    return out


def reverse(a: Array) -> Array:
    return np.array([v * (-1) ** (i.bit_count() * (i.bit_count() - 1) // 2) for i, v in enumerate(a)])


def basis(mask: int) -> Array:
    out = np.zeros(16)
    out[mask] = 1.0
    return out


def motor(yaw_rad: float, translation_mm: Vector3) -> Array:
    rotor = math.cos(yaw_rad / 2) * basis(0) - math.sin(yaw_rad / 2) * basis(6)
    translator = basis(0) + sum(0.5 * t * basis(1 | (1 << (i + 1))) for i, t in enumerate(translation_mm))
    result = gp(translator, rotor)
    if not np.isfinite(result).all() or not np.allclose(gp(result, reverse(result)), basis(0), atol=1e-10):
        raise ValueError("MOTOR_NORM_INVALID")
    return result


def transform(point_mm: Vector3, pose: Array) -> Vector3:
    x, y, z = point_mm
    point = basis(14) + x * basis(13) - y * basis(11) + z * basis(7)
    result = gp(gp(pose, point), reverse(pose))
    if abs(result[14]) < 1e-12 or not np.isfinite(result).all():
        raise ValueError("POINT_TRANSFORM_INVALID")
    return (float(result[13] / result[14]), float(-result[11] / result[14]), float(result[7] / result[14]))


class Calibration(Contract):
    calibration_id: Identifier = "sil-calibration-v1"
    pixel_to_mm: Positive = 0.1
    yaw_rad: Finite = 0.0
    translation_mm: Vector3 = (0.0, 0.0, 10.0)

    def pixel_to_base(self, x: float, y: float) -> Vector3:
        """FF-PGA-01; reference parity: FF-V6-XFORM-01 coordinate composition."""
        return transform((x * self.pixel_to_mm, y * self.pixel_to_mm, 0.0), motor(self.yaw_rad, self.translation_mm))
