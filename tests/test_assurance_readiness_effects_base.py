"""Shared test_assurance_readiness_effects primitives and declarations."""





from hmt_edge_robot.assurance.contracts import (
    Effect,
    EffectContract,
    EffectTrace,
    Epochs,
    RecoverySpec,
    RecoveryTrace,
    StageObservation,
)
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
