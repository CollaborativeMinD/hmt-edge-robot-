"""REQ-NG-01..03: calibrated PCA candidates, degeneracy rejection, provenance.

Pipeline adapted from Neuro-Grasp's threshold/contour/PCA functions.
"""

from __future__ import annotations

import hashlib
import math

import cv2
import numpy as np
from numpy.typing import NDArray

from .contracts import GraspObservation
from .geometry import Calibration


class NeuroGrasp:
    def __init__(
        self, calibration: Calibration, min_area: float = 100.0, ambiguity_limit: float = 0.8
    ) -> None:
        if not math.isfinite(min_area) or min_area <= 0 or not 0 < ambiguity_limit < 1:
            raise ValueError("VISION_CONFIG_INVALID")
        self.calibration, self.min_area, self.ambiguity_limit = (
            calibration,
            min_area,
            ambiguity_limit,
        )

    def candidates(self, frame: NDArray[np.uint8], limit: int = 8) -> tuple[GraspObservation, ...]:
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("CANDIDATE_LIMIT_INVALID")
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("FRAME_FORMAT_INVALID")
        if not 16 <= frame.shape[0] <= 2048 or not 16 <= frame.shape[1] <= 2048:
            raise ValueError("FRAME_SIZE_INVALID")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda c: (-cv2.contourArea(c), cv2.boundingRect(c)))
        frame_hash = hashlib.sha256(frame.tobytes()).hexdigest()
        observations = []
        for contour in contours[:32]:
            if cv2.contourArea(contour) < self.min_area:
                continue
            observation = self._pose(contour, frame_hash)
            if observation is not None:
                observations.append(observation)
            if len(observations) == limit:
                break
        return tuple(observations)

    def _pose(self, contour: NDArray[np.int32], frame_hash: str) -> GraspObservation | None:
        points = contour.reshape(-1, 2).astype(float)
        if len(points) < 3:
            return None
        mean = points.mean(axis=0)
        covariance = np.cov(points, rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        major, minor = float(eigenvalues[1]), max(0.0, float(eigenvalues[0]))
        if major <= 1e-12 or minor / major >= self.ambiguity_limit:
            return None
        vector = eigenvectors[:, 1]
        angle = (
            math.degrees(math.atan2(float(vector[1]), float(vector[0])))
            + math.degrees(self.calibration.yaw_rad)
        ) % 180.0
        target = self.calibration.pixel_to_base(float(mean[0]), float(mean[1]))
        return GraspObservation(
            target_mm=target,
            angle_deg=angle,
            primary_eigenvalue=major,
            secondary_eigenvalue=minor,
            ambiguity_ratio=minor / major,
            calibration_id=self.calibration.calibration_id,
            frame_hash=frame_hash,
        )


def synthetic_frame() -> NDArray[np.uint8]:
    """Deterministic SIL source; never substituted for a physical camera."""
    frame = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.rectangle(frame, (40, 50), (180, 90), (255, 255, 255), -1)
    return frame
