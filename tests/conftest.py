import secrets
from dataclasses import dataclass

import pytest

from hmt_edge_robot.contracts import MotionRequest, Policy
from hmt_edge_robot.runtime import RobotCell

TOKEN = secrets.token_hex(24)


@dataclass
class Clock:
    now: float = 10.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cell(tmp_path, clock):
    value = RobotCell(tmp_path / "cell.db", TOKEN, clock=clock)
    yield value
    value.close()


@pytest.fixture
def ready(cell):
    session = cell.access.login("operator", TOKEN, cell.clock())
    cell.observe_simulation(0)
    return session


def request(cell, session, request_id="task-1", **changes):
    payload = dict(
        request_id=request_id,
        operator_id="operator",
        session_id=session,
        policy_epoch=cell.policy.policy_epoch,
        target_mm=(10.0, 20.0, 10.0),
        speed_mps=0.1,
        issued_at=cell.clock(),
        expires_at=cell.clock() + 2.0,
    )
    payload.update(changes)
    return MotionRequest(**payload)


def policy(**changes):
    return Policy(**changes)
