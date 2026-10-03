"""test_assurance_readiness_effects: optimization interface."""


from itertools import combinations

import pytest
from pydantic import ValidationError
from test_assurance_readiness_effects_base import HASH, effect_contract, spec

from hmt_edge_robot.assurance.contracts import (
    Epochs,
    RecoverySpec,
    WarmCandidate,
    WitnessScope,
)
from hmt_edge_robot.assurance.optimization import optimize_warm_set


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
