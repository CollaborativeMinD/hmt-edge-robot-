"""test_assurance_readiness_effects: readiness interface."""

import asyncio

import pytest
from test_assurance_readiness_effects_base import HASH, spec, trace

from hmt_edge_robot.assurance.contracts import (
    Epochs,
    RecoverySpec,
    StageObservation,
)
from hmt_edge_robot.contracts import digest


def test_mcc_mission_readiness_and_boundary(cell):
    s = spec(reserve_sec=5.0)
    t = trace(cell, s)
    result = cell.assurance.mcc.assess(s, t)
    assert result.report.verdict == "RECOVERY_PATH_NOT_AFFORDABLE"
    s = spec(reserve_sec=4.0)
    result = cell.assurance.mcc.assess(s, t)
    assert result.report.verdict == "MISSION_READY"
    assert result.report_hash == digest(result.report.model_dump(mode="json"))
    assert cell.assurance.kernel.notices()[-1]["report_hash"] == result.report_hash
    assert cell.ledger.verify() == 2

@pytest.mark.parametrize("stage,verdict", [
    ("image_available", "IMAGE_UNAVAILABLE"), ("policy_loaded", "POLICY_LOAD_FAILED"),
    ("model_loaded", "MODEL_LOAD_EXCEEDS_HORIZON"), ("container_started", "FIRST_TRANSACTION_FAILED"),
])
def test_mcc_stage_failure(cell, stage, verdict):
    s = spec()
    t = trace(cell, s)
    observations = tuple(o.model_copy(update={"succeeded": False}) if o.stage == stage else o for o in t.observations)
    assert cell.assurance.mcc.assess(s, t.model_copy(update={"observations": observations})).report.verdict == verdict

@pytest.mark.parametrize("mode", ["empty", "order", "transaction", "epoch", "expired", "future"])
def test_mcc_incomplete_invalid_and_stale(cell, clock, mode):
    s, t = spec(), trace(cell, spec())
    if mode == "empty":
        t = t.model_copy(update={"observations": ()})
    elif mode == "order":
        t = t.model_copy(update={"observations": tuple(reversed(t.observations))})
    elif mode == "transaction":
        t = t.model_copy(update={"observations": t.observations[:-1]+(t.observations[-1].model_copy(update={"transaction_hash": digest("wrong")}),)})
    elif mode == "epoch":
        t = t.model_copy(update={"epochs": Epochs(policy=2)})
    elif mode == "expired":
        clock.now = 61.0
    else:
        t = t.model_copy(update={"started_at": 20.0})
    assert cell.assurance.mcc.assess(s, t).report.verdict != "MISSION_READY"

def test_mcc_software_probe_and_timeout(cell, clock):
    async def probe(stage):
        clock.now += .1
        return StageObservation(stage=stage, elapsed_sec=0.0, succeeded=True,
            transaction_hash=HASH if stage == "first_valid_transaction" else None)
    s = spec()
    t = asyncio.run(cell.assurance.mcc.collect(s, probe))
    assert cell.assurance.mcc.assess(s, t).report.verdict == "MISSION_READY"
    async def stalled(stage):
        await asyncio.sleep(.03)
        return StageObservation(stage=stage, elapsed_sec=0.0, succeeded=True)
    short = RecoverySpec(capability_id="mission", capability_hash=HASH, transaction_hash=HASH,
        recovery_horizon_sec=.01)
    t = asyncio.run(cell.assurance.mcc.collect(short, stalled))
    assert not t.observations[-1].succeeded
    assert cell.assurance.mcc.assess(short, t).report.verdict != "MISSION_READY"

def test_mcc_empirical_envelope_is_not_wcet(cell):
    s = spec()
    result = cell.assurance.mcc.envelope(s, (trace(cell, s),)*8)
    assert result["sample_count"] == 8 and result["p95_sec"] == 5.0
    assert 0 < result["failure_probability_upper_95"] < 1
    assert result["worst_case_guarantee"] is False
    with pytest.raises(ValueError):
        cell.assurance.mcc.envelope(s, ())
