import pytest
from conftest import TOKEN

from hmt_edge_robot.contracts import Lane, Policy, PositionPacket, SensorSample
from hmt_edge_robot.safety import HaloSafe


def packet(position, seq=0, time=10.0, frame="robot-base"):
    return PositionPacket(position_mm=position, monotonic_seq=seq, observed_at=time, frame_id=frame)


def test_access_auth_scope_expiry_and_revocation(cell, clock):
    for operator, proof in (("ghost", TOKEN), ("operator", "wrong")):
        with pytest.raises(PermissionError):
            cell.access.login(operator, proof, clock())
    session = cell.access.login("operator", TOKEN, clock())
    assert cell.access.authorize(session, "operator", "motion", clock())
    assert not cell.access.authorize(session, "ghost", "motion", clock())
    assert not cell.access.authorize(session, "operator", "invented", clock())
    clock.now += 0.5
    assert cell.access.heartbeat(session, "operator", clock())
    clock.now += 1.0
    assert not cell.access.authorize(session, "operator", "motion", clock())
    assert not cell.access.heartbeat(session, "operator", clock())
    cell.access.revoke(session)
    assert not cell.access.authorize(session, "operator", "motion", clock())


def test_access_clock_and_capacity(cell, clock):
    cell.access.policy = Policy(max_queue_size=1)
    cell.access.login("operator", TOKEN, clock())
    with pytest.raises(PermissionError):
        cell.access.login("operator", TOKEN, clock())
    with pytest.raises(ValueError):
        cell.access.authorize("x", "operator", "inspect", 0.0)
    assert not cell.access.sessions
    session = cell.access.login("operator", TOKEN, 10.0)
    assert not cell.access.authorize(session, "operator", "inspect", 310.0)
    assert cell.access.login("operator", TOKEN, 310.0)


def test_safety_path_distance_not_endpoint():
    safety = HaloSafe(Policy(workspace_max_mm=(3000.0, 100.0, 100.0)))
    safety.update(packet((0.0, 0.0, 0.0)), packet((1500.0, 0.0, 0.0)), 10.0)
    assert not safety.assess((3000.0, 0.0, 0.0), 0.1, 10.0).admitted
    assert safety.assess((0.0, 0.0, 0.0), 0.1, 10.0).admitted


@pytest.mark.parametrize(
    "human,expected",
    [((3000.0, 0.0, 0.0), 1.0), ((1000.0, 0.0, 0.0), None), ((100.0, 0.0, 0.0), 0.0)],
)
def test_safety_scaling(human, expected):
    safety = HaloSafe(Policy())
    safety.update(packet((0.0, 0.0, 0.0)), packet(human), 10.0)
    assessment = safety.assess((0.0, 0.0, 0.0), 0.1, 10.0)
    if expected is None:
        assert 0 < assessment.scale_factor < 1
    else:
        assert assessment.scale_factor == expected


def test_safety_invalid_stale_frame_and_reset():
    safety = HaloSafe(Policy())
    assert safety.assess((0.0, 0.0, 0.0), 0.1, 10.0).rejection_reason == "OBSERVATION_MISSING"
    with pytest.raises(ValueError):
        safety.update(packet((0.0, 0.0, 0.0), frame="camera"), packet((3000.0, 0.0, 0.0)), 10.0)
    assert safety.latched
    safety.update(packet((0.0, 0.0, 0.0)), packet((3000.0, 0.0, 0.0)), 10.0)
    assert safety.reset((0.0, 0.0, 0.0), 10.0)
    assert safety.assess((0.0, 0.0, 0.0), 0.1, 11.0).rejection_reason == "OBSERVATION_STALE"
    assert safety.assess((0.0, 0.0, 0.0), 1.0, 10.0).rejection_reason == "SPEED_NOT_ADMITTED"
    assert safety.assess((1000.0, 0.0, 0.0), 0.1, 10.0).rejection_reason == "WORKSPACE_REJECTED"
    with pytest.raises(ValueError):
        safety.update(packet((0.0, 0.0, 0.0)), packet((3000.0, 0.0, 0.0)), 10.0)
    assert not safety.reset((0.0, 0.0, 0.0), 11.0)
    with pytest.raises(ValueError):
        HaloSafe(Policy()).update(packet((0.0, 0.0, 0.0)), packet((3000.0, 0.0, 0.0)), 11.0)


def sample(seq, voltage=4.1, temp=45.0, time=10.0):
    return SensorSample(
        monotonic_seq=seq, observed_at=time, voltage_v=voltage, temp_c=temp, signal_dbm=-50.0
    )


def test_edge_lanes_gaps_hysteresis_halt(cell):
    assert cell.edge.process(sample(0), 10.0).pace_lane == Lane.PRIMARY
    assert cell.edge.process(sample(1, 3.7), 10.0).pace_lane == Lane.ALTERNATE
    assert cell.edge.process(sample(2, 3.72), 10.0).pace_lane == Lane.ALTERNATE
    assert cell.edge.process(sample(3, 3.76), 10.0).pace_lane == Lane.PRIMARY
    gap = cell.edge.process(sample(4, temp=86.0), 10.0)
    assert gap.pace_lane == Lane.CONTINGENCY and gap.accepted_temp_c is None
    assert not gap.data_valid
    assert cell.edge.process(sample(5, 3.4), 10.0).flush_required
    with pytest.raises(RuntimeError):
        cell.edge.process(sample(6), 10.0)
    assert cell.ledger.verify() == 6


def test_edge_sequence_age_and_history_bounds(cell):
    cell.edge.process(sample(0), 10.0)
    with pytest.raises(ValueError):
        cell.edge.process(sample(0), 10.0)
    with pytest.raises(ValueError):
        cell.edge.process(sample(1), 11.0)
    for seq in range(1, 300):
        cell.edge.process(sample(seq), 10.0)
    assert len(cell.edge.history) == cell.policy.max_history_records
