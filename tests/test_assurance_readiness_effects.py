"""Requirements first: adversarial software readiness and effect observation acceptance."""
import asyncio
from itertools import combinations

import pytest
from pydantic import ValidationError

from hmt_edge_robot.assurance.contracts import (
    Effect,
    EffectContract,
    EffectTrace,
    Epochs,
    RecoverySpec,
    RecoveryTrace,
    StageObservation,
    WarmCandidate,
    WitnessScope,
)
from hmt_edge_robot.assurance.optimization import optimize_warm_set
from hmt_edge_robot.assurance.usea import file_manifest, manifest_effects
from hmt_edge_robot.contracts import digest

HASH = digest("qualified-software")


def spec(**kwargs):
    return RecoverySpec(capability_id="mission", capability_hash=HASH, transaction_hash=HASH,
                        recovery_horizon_sec=10.0, **kwargs)


def trace(cell, specification, **kwargs):
    observations = tuple(StageObservation(stage=stage, elapsed_sec=float(i), succeeded=True,
        transaction_hash=HASH if stage == "first_valid_transaction" else None)
        for i, stage in enumerate(specification.stages))
    return RecoveryTrace(origin="SOFTWARE_COLLECTED", collector_id="software-fixture", epochs=Epochs(), started_at=0.0,
                         observations=observations, **kwargs)


def effect_contract(**kwargs):
    values = dict(executable_id="mission", executable_hash=HASH,
        allowed=(Effect(kind="write", target="evidence/report.json"),),
        required_coverage=("write", "network", "spawn"), max_runtime_sec=2.0)
    values.update(kwargs)
    return EffectContract.model_validate(values)


def effect_trace(**kwargs):
    values = dict(origin="SOFTWARE_COLLECTED", collector_id="software-fixture", executable_hash=HASH, epochs=Epochs(),
        started_at=0.0, runtime_sec=1.0, exit_code=0, coverage=("write", "network", "spawn"),
        complete=True, observed=(Effect(kind="write", target="evidence/report.json"),))
    values.update(kwargs)
    return EffectTrace.model_validate(values)


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


def test_usea_effect_receipt_distinction(cell):
    result = cell.assurance.usea.attest(effect_contract(), effect_trace())
    assert result.report.verdict == "DECLARED_EFFECT_CONFIRMED"
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(observed=(Effect(kind="network", target="10.0.0.12:443"),)))
    assert result.report.verdict == "SIDE_EFFECT_OUTSIDE_CONTRACT"
    assert "UNDECLARED_NETWORK_ACCESS" in result.report.reason_codes
    assert cell.assurance.kernel.notices()[-1]["requires_ack"]


@pytest.mark.parametrize("changes", [
    {"complete": False}, {"coverage": ("write",)}, {"executable_hash": digest("other")},
    {"epochs": Epochs(policy=2)}, {"started_at": 100.0},
])
def test_usea_incomplete_is_hold(cell, changes):
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(**changes))
    assert result.report.verdict == "ATTESTATION_INCOMPLETE"


@pytest.mark.parametrize("changes", [{"runtime_sec": 3.0}, {"exit_code": 1}])
def test_usea_runtime_and_exit_contract(cell, changes):
    assert cell.assurance.usea.attest(effect_contract(), effect_trace(**changes)).report.verdict == "SIDE_EFFECT_OUTSIDE_CONTRACT"


def test_manifest_actual_writes_and_coverage_limit(tmp_path, cell):
    before = file_manifest(tmp_path)
    (tmp_path/"report.json").write_text("payload")
    after = file_manifest(tmp_path)
    effects = manifest_effects(before, after)
    assert effects == (Effect(kind="write", target="report.json"),)
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(observed=effects, coverage=("write",), complete=False))
    assert result.report.verdict != "DECLARED_EFFECT_CONFIRMED"
    (tmp_path/"link").symlink_to(tmp_path/"report.json")
    with pytest.raises(ValueError, match="MANIFEST_INCOMPLETE"):
        file_manifest(tmp_path)


def test_manifest_resource_bounds(tmp_path):
    (tmp_path/"a").write_bytes(b"1234")
    with pytest.raises(ValueError, match="BYTE_BOUND"):
        file_manifest(tmp_path, max_bytes=3)
    (tmp_path/"b").write_bytes(b"x")
    with pytest.raises(ValueError):
        file_manifest(tmp_path, max_files=1)
    with pytest.raises(ValueError):
        file_manifest(tmp_path, max_files=0)
    with pytest.raises(ValueError):
        manifest_effects({str(i):HASH for i in range(257)}, {})


def test_optimization_exact_against_brute_force():
    candidates = tuple(WarmCandidate(artifact_id=f"model-{i}", cost_units=i+1, saved_sec=float(i*i+1)) for i in range(6))
    for budget in range(12):
        result = optimize_warm_set(candidates, budget)
        subsets = [s for n in range(7) for s in combinations(candidates, n)]
        best = max(sum(c.saved_sec for c in s) for s in subsets if sum(c.cost_units for c in s) <= budget)
        assert result["saved_sec"] == best
        assert len(result["selected"]) == len(set(result["selected"]))
    with pytest.raises(ValueError):
        optimize_warm_set(candidates, 1025)
    with pytest.raises(ValueError):
        optimize_warm_set(candidates+candidates, 3)


def test_assurance_contracts_strict_finite_frozen():
    with pytest.raises(ValidationError):
        spec(reserve_sec=float("nan"))
    with pytest.raises(ValidationError):
        RecoverySpec(capability_id="a", capability_hash=HASH, transaction_hash=HASH, recovery_horizon_sec=1.0, stages=("ready", "ready"))
    with pytest.raises(ValidationError):
        effect_contract(required_coverage=("write", "write"))
    with pytest.raises(ValidationError):
        WitnessScope(subject_id="a", subject_hash=HASH, contract_hash=HASH, collector_id="fixture", epochs=Epochs(), observed_at=1.0, expires_at=1.0, coverage=())
    with pytest.raises(ValidationError):
        Epochs.model_validate({"policy": "1"})
    with pytest.raises(ValidationError):
        Epochs.model_validate({"unrecognized": True})
    frozen = Epochs()
    with pytest.raises(ValidationError):
        setattr(frozen, "policy", 2)
