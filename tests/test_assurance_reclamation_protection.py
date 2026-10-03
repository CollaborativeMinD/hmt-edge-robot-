"""test_assurance_reclamation: protection interface."""

import pytest
from test_assurance_reclamation_base import plan, setup_artifact

from hmt_edge_robot.assurance.contracts import Census, Epochs
from hmt_edge_robot.contracts import digest


def test_agc_transitive_reference_closure_and_cycles(cell):
    a = setup_artifact(cell, authority_refs=("live-lease",), dependencies=("dependency",))
    catalog = cell.assurance.catalog
    b = catalog.put("dependency", b"dependency")
    catalog.update(b.model_copy(update={"dependencies": ("model",)}))
    catalog.put("old-export", b"stale")
    decisions = {d.scope.subject_id:d.verdict for d in plan(cell).decisions}
    assert decisions == {"dependency":"LIVE", "model":"LIVE", "old-export":"SAFE_TO_RECLAIM"}
    assert catalog.verify() == 3
    catalog.update(a.model_copy(update={"authority_refs": (), "recovery_refs": ("rollback",)}))
    assert {d.verdict for d in plan(cell).decisions} == {"RECOVERY_REQUIRED", "SAFE_TO_RECLAIM"}

@pytest.mark.parametrize("refs,verdict", [
    ({"authority_refs": ("lease",)}, "LIVE"), ({"recovery_refs": ("rollback",)}, "RECOVERY_REQUIRED"),
    ({"cold_start_refs": ("atlas",)}, "RECOVERY_REQUIRED"), ({"evidence_refs": ("ledger",)}, "EVIDENCE_REQUIRED"),
    ({"side_effect_refs": ("execution",)}, "EVIDENCE_REQUIRED"), ({"dependencies": ("unknown",)}, "UNKNOWN_HOLD"),
])
def test_agc_reference_protection(cell, refs, verdict):
    setup_artifact(cell, **refs)
    assert plan(cell).decisions[0].verdict == verdict

@pytest.mark.parametrize("mode", ["incomplete", "epoch", "expired", "future", "record_epoch"])
def test_agc_unknown_hold(cell, clock, mode):
    record = setup_artifact(cell)
    census = cell.assurance.catalog.census()
    changes = {"incomplete": {"complete": False}, "epoch": {"epochs": Epochs(policy=2)},
               "expired": {}, "future": {"observed_at": 11.0},
               "record_epoch": {"records": (record.model_copy(update={"epochs": Epochs(policy=2)}),)}}
    if mode == "expired":
        clock.now = 71.0
    census = census.model_copy(update=changes[mode])
    assert cell.assurance.agc.plan(census).decisions[0].verdict == "UNKNOWN_HOLD"

def test_catalog_and_census_bounds(cell):
    record = setup_artifact(cell)
    with pytest.raises(ValueError):
        cell.assurance.catalog.put("big", bytes(16_777_217))
    with pytest.raises(ValueError):
        cell.assurance.catalog.census(ttl_sec=0.0)
    with pytest.raises(ValueError):
        cell.assurance.catalog.update(record.model_copy(update={"identity": record.identity.model_copy(update={"identity_hash": digest("other")})}))
    with pytest.raises(ValueError):
        cell.assurance.catalog._row("absent")
    with pytest.raises(ValueError):
        Census(epochs=Epochs(),revision=0,observed_at=0.0,expires_at=1.0,complete=True,records=(record,record))
