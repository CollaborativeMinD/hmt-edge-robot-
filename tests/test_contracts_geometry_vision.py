"""test_contracts_geometry: vision interface."""

import math

import numpy as np
import pytest

from hmt_edge_robot.geometry import Calibration
from hmt_edge_robot.safety import AdmittanceController
from hmt_edge_robot.vision import NeuroGrasp, synthetic_frame


def test_grasp_candidates_calibration_determinism():
    vision = NeuroGrasp(Calibration(yaw_rad=math.pi / 2))
    candidates = vision.candidates(synthetic_frame())
    assert candidates == vision.candidates(synthetic_frame())
    assert len(candidates) == 1
    np.testing.assert_allclose(candidates[0].target_mm, (-7.0, 11.0, 10.0), atol=1e-10)
    assert candidates[0].angle_deg == 90.0

def test_vision_rejects_ambiguity_empty_small_and_format():
    vision = NeuroGrasp(Calibration())
    square = np.zeros((64, 64, 3), dtype=np.uint8)
    square[10:40, 10:40] = 255
    assert vision.candidates(square) == ()
    assert vision.candidates(np.zeros_like(square)) == ()
    square[:] = 0
    square[10:12, 10:12] = 255
    assert vision.candidates(square) == ()
    for frame in (
        np.zeros((3, 3, 3), dtype=np.uint8),
        np.zeros((32, 32)),
        np.zeros((4096, 16, 3), dtype=np.uint8),
    ):
        with pytest.raises(ValueError):
            vision.candidates(frame)
    with pytest.raises(ValueError):
        vision.candidates(square, 0)
    with pytest.raises(ValueError):
        NeuroGrasp(Calibration(), min_area=0)
    assert vision._pose(np.array([[[1, 1]], [[2, 2]]]), "0" * 64) is None

def test_admittance_law_and_bounds():
    controller = AdmittanceController(mass=5.0, damping=0.0, dt=0.01)
    position, velocity = controller.step((10.0, 0.0, 0.0))
    np.testing.assert_allclose(velocity, (0.02, 0.0, 0.0))
    np.testing.assert_allclose(position, (0.0002, 0.0, 0.0))
    for cfg in (dict(mass=0.0), dict(dt=1.0), dict(damping=-1.0), dict(mass=float("nan"))):
        with pytest.raises(ValueError):
            AdmittanceController(**cfg)
    with pytest.raises(ValueError):
        controller.step((float("nan"), 0.0, 0.0))
