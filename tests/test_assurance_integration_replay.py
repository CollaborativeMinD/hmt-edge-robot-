"""test_assurance_integration: replay interface."""



import pytest
from conftest import TOKEN
from test_assurance_readiness_effects import effect_contract, effect_trace, spec

from hmt_edge_robot.runtime import RobotCell


def test_witness_binding_atomic_unknown_reference(cell, ready):
    cell.assurance.catalog.put("known", b"a")
    report = cell.assurance.usea.attest(effect_contract(), effect_trace(artifact_refs=("known", "missing")))
    revision = cell.assurance.catalog.census().revision
    with pytest.raises(ValueError):
        cell.assurance.bind_witness(report, ready, "operator")
    census = cell.assurance.catalog.census()
    assert census.revision == revision and not census.records[0].side_effect_refs

def test_catalog_readonly_no_recovery_or_writes(cell, tmp_path, clock):
    cell.assurance.catalog.put("model", b"data")
    before = cell.ledger.verify()
    readonly = RobotCell(cell.ledger.path, TOKEN, clock=clock, read_only=True)
    try:
        assert readonly.assurance.catalog.census().records[0].identity.artifact_id == "model"
        assert readonly.ledger.verify() == before
        assert readonly.assurance.catalog.verify() == 1
    finally:
        readonly.close()

def test_software_probe_durable_failure_and_no_returned_readiness(cell):
    import asyncio

    from hmt_edge_robot.assurance.contracts import StageObservation
    async def broken(stage):
        return StageObservation(stage="wrong-stage", elapsed_sec=0.0, succeeded=True)
    with pytest.raises(ValueError, match="PROBE_STAGE_MISMATCH"):
        asyncio.run(cell.assurance.mcc.collect(spec(), broken))
    assert cell.ledger.recent()[0]["packet_type"] == "recovery_probe_intent"
    assert cell.assurance.kernel.notices()[-1]["reason_codes"] == ["PROBE_FAILED"]

def test_catalog_storage_fail_closed(cell):
    from hmt_edge_robot.ledger import EvidenceError
    with cell.ledger.db:
        cell.ledger.db.execute("DROP TABLE assurance_catalog")
    with pytest.raises(EvidenceError, match="STORAGE_UNAVAILABLE"):
        cell.assurance.catalog.put("model", b"x")

def test_catalog_duplicate_and_expired_grant(cell, ready, clock):
    cell.assurance.catalog.put("model", b"x")
    with pytest.raises(ValueError, match="ALREADY_REGISTERED"):
        cell.assurance.catalog.put("model", b"x")
    current = cell.assurance.agc.plan(cell.assurance.catalog.census())
    grant = cell.assurance.issue_grant(current, "quarantine", "model", ready, "operator")
    clock.now = grant.expires_at
    with pytest.raises(PermissionError):
        cell.assurance.mutate(current, grant)
    clock.now = current.expires_at
    with pytest.raises(PermissionError, match="PLAN_STALE"):
        cell.assurance.issue_grant(current, "delete", "model", cell.access.login("operator",TOKEN,clock()), "operator")
