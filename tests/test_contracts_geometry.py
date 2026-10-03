"""Compatibility facade for the decomposed test_contracts_geometry interfaces."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from hmt_edge_robot.contracts import MotionRequest, Policy, PositionPacket, canonical
from hmt_edge_robot.geometry import basis, gp, motor, reverse, transform


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_boundary_rejected(value):
    with pytest.raises(ValidationError):
        PositionPacket(position_mm=(value, 0.0, 0.0), monotonic_seq=0, observed_at=0.0)
    with pytest.raises(ValueError):
        canonical({"value": value})

def test_contracts_forbid_unknown_mutation_coercion():
    with pytest.raises(ValidationError):
        Policy.model_validate({"unknown": 1})
    with pytest.raises(ValidationError):
        Policy.model_validate({"policy_epoch": "1"})
    with pytest.raises(ValidationError):
        setattr(Policy(), "policy_epoch", 3)
    with pytest.raises(ValidationError):
        MotionRequest(
            request_id="x",
            operator_id="o",
            session_id="s",
            policy_epoch=1,
            target_mm=(0.0, 0.0, 0.0),
            speed_mps=0.1,
            issued_at=2.0,
            expires_at=1.0,
        )

@pytest.mark.parametrize(
    "changes",
    [
        dict(workspace_min_mm=(100.0, 0.0, 0.0)),
        dict(min_separation_m=3.0),
        dict(safe_voltage_v=4.0),
        dict(heartbeat_timeout_sec=400.0),
    ],
)
def test_policy_ordering(changes):
    with pytest.raises(ValidationError):
        Policy(**changes)

@pytest.mark.parametrize("yaw", [0.0, 0.4, math.pi / 2, -2.0])
def test_pga_classical_parity_and_inverse(yaw):
    translation = (11.0, -8.0, 4.0)
    pose = motor(yaw, translation)
    np.testing.assert_allclose(gp(pose, reverse(pose)), basis(0), atol=1e-10)
    point = (4.0, 8.0, -2.0)
    result = transform(point, pose)
    expected = (
        math.cos(yaw) * point[0] - math.sin(yaw) * point[1] + translation[0],
        math.sin(yaw) * point[0] + math.cos(yaw) * point[1] + translation[1],
        point[2] + translation[2],
    )
    np.testing.assert_allclose(result, expected, atol=1e-10)
    np.testing.assert_allclose(transform(result, reverse(pose)), point, atol=1e-10)

def test_invalid_motor_point():
    with pytest.raises(ValueError):
        motor(float("nan"), (0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        transform((0.0, 0.0, 0.0), np.zeros(16))
