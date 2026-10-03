"""Governed lifecycle, atomic fencing, reconstruction, reference closure and evidence failure."""

import pytest
from conftest import TOKEN

from hmt_edge_robot.assurance.contracts import Census, Epochs
from hmt_edge_robot.contracts import Policy, digest
from hmt_edge_robot.ledger import EvidenceError


def setup_artifact(cell, **refs):
    catalog = cell.assurance.catalog
    record = catalog.put("model", b"weights")
    if refs:
        record = record.model_copy(update=refs)
        catalog.update(record)
    return record


def plan(cell):
    return cell.assurance.agc.plan(cell.assurance.catalog.census())


def grant(cell, current, action, session):
    return cell.assurance.issue_grant(current, action, "model", session, "operator")


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


def test_agc_dry_run_quarantine_restore_and_governed_delete(cell, clock):
    setup_artifact(cell)
    session = cell.access.login("operator", TOKEN, clock())
    p = plan(cell)
    assert p.dry_run is True and cell.assurance.catalog._row("model")[3] == "ACTIVE"
    assert cell.assurance.catalog.read("model") == b"weights"
    q = cell.assurance.mutate(p, grant(cell, p, "quarantine", session))
    assert q.report.verdict == "QUARANTINE" and not q.report.dry_run
    assert cell.assurance.catalog._row("model")[2] == b"weights"
    with pytest.raises(PermissionError, match="NOT_ACTIVE"):
        cell.assurance.catalog.read("model")
    p = plan(cell)
    with pytest.raises(PermissionError, match="TRANSITION"):
        cell.assurance.mutate(p, grant(cell, p, "delete", session))
    restored = cell.assurance.mutate(p, grant(cell, p, "restore", session))
    assert restored.report.verdict == "RESTORED"
    assert cell.assurance.catalog.read("model") == b"weights"
    p = plan(cell)
    cell.assurance.mutate(p, grant(cell, p, "quarantine", session))
    clock.now += 60.0
    session = cell.access.login("operator", TOKEN, clock())
    p = plan(cell)
    result = cell.assurance.mutate(p, grant(cell, p, "delete", session))
    assert result.report.verdict == "RECLAIMED"
    assert cell.assurance.catalog._row("model")[2] is None
    assert cell.assurance.catalog.census().records == ()
    assert cell.assurance.catalog.verify() == 1


def test_agc_fence_changed_reference_and_no_grant_replay(cell, ready):
    record = setup_artifact(cell)
    p = plan(cell)
    g = grant(cell, p, "quarantine", ready)
    cell.assurance.catalog.update(record.model_copy(update={"recovery_refs": ("new-rollback",)}))
    with pytest.raises(PermissionError, match="FENCE"):
        cell.assurance.mutate(p, g)
    assert cell.assurance.catalog._row("model")[3] == "ACTIVE"
    cell.assurance.catalog.update(record)
    p = plan(cell)
    g = grant(cell, p, "quarantine", ready)
    cell.assurance.mutate(p, g)
    with pytest.raises(PermissionError):
        cell.assurance.mutate(p, g)
    assert cell.assurance.kernel.notices()[-1]["severity"] == "ALERT"


def test_agc_authority_revoked_and_policy_epoch_changed(cell, ready):
    setup_artifact(cell)
    p = plan(cell)
    g = grant(cell, p, "quarantine", ready)
    cell.access.revoke(ready)
    with pytest.raises(PermissionError):
        cell.assurance.mutate(p, g)
    with pytest.raises(PermissionError):
        cell.assurance.issue_grant(p, "delete", "model", ready, "operator")
    session = cell.access.login("operator", TOKEN, cell.clock())
    g = grant(cell, p, "quarantine", session)
    cell.update_policy(Policy(policy_epoch=2), session, "operator")
    with pytest.raises(PermissionError):
        cell.assurance.mutate(p, g)
    assert plan(cell).decisions[0].verdict == "UNKNOWN_HOLD"


def test_agc_plan_reconstruction_and_forged_grant(cell, ready):
    setup_artifact(cell)
    p = plan(cell)
    fake = p.model_copy(update={"census_hash": digest("false")})
    g = grant(cell, fake, "quarantine", ready)
    with pytest.raises(PermissionError, match="RECONSTRUCTION"):
        cell.assurance.mutate(fake, g)
    good = grant(cell, p, "quarantine", ready)
    with pytest.raises(PermissionError, match="FENCE"):
        cell.assurance.mutate(p, good.model_copy(update={"action":"delete"}))
    assert cell.assurance.catalog._row("model")[3] == "ACTIVE"


def test_agc_reference_added_during_quarantine_blocks_delete(cell, clock):
    record = setup_artifact(cell)
    session = cell.access.login("operator", TOKEN, clock())
    p = plan(cell)
    cell.assurance.mutate(p, grant(cell, p, "quarantine", session))
    cell.assurance.catalog.update(record.model_copy(update={"evidence_refs": ("audit",)}))
    assert cell.assurance.catalog.verify() == 1
    clock.now += 60
    session = cell.access.login("operator", TOKEN, clock())
    p = plan(cell)
    with pytest.raises(PermissionError):
        cell.assurance.mutate(p, grant(cell, p, "delete", session))
    assert cell.assurance.catalog._row("model")[2] == b"weights"
    # Restoration is admitted even when new references make the artifact protected.
    assert cell.assurance.mutate(p, grant(cell, p, "restore", session)).report.verdict == "RESTORED"


def test_catalog_content_projection_tampering(cell):
    setup_artifact(cell)
    with cell.ledger.db:
        cell.ledger.db.execute("UPDATE assurance_catalog SET content=?", (b"tampered",))
    with pytest.raises(EvidenceError, match="CONTENT_HASH"):
        cell.assurance.catalog.verify()
    with cell.ledger.db:
        cell.ledger.db.execute("UPDATE assurance_catalog SET content=?,state='QUARANTINE'", (b"weights",))
    with pytest.raises(EvidenceError, match="PROJECTION"):
        cell.assurance.catalog.verify()


def test_agc_evidence_failure_rolls_back_mutation(cell, ready, monkeypatch):
    setup_artifact(cell)
    p = plan(cell)
    g = grant(cell, p, "quarantine", ready)
    original = cell.ledger._append
    def failing(producer, request_id, kind, payload):
        if kind == "artifact_mutated":
            raise EvidenceError("INJECTED_EVIDENCE_FAILURE")
        return original(producer, request_id, kind, payload)
    monkeypatch.setattr(cell.ledger, "_append", failing)
    with pytest.raises(EvidenceError):
        cell.assurance.mutate(p, g)
    assert cell.assurance.catalog._row("model")[3] == "ACTIVE"
    assert cell.ledger.db.execute("SELECT consumed FROM assurance_grants WHERE grant_id=?", (g.grant_id,)).fetchone()[0] == 0
    monkeypatch.setattr(cell.ledger, "_append", original)
    assert cell.assurance.catalog.verify() == 1


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


def test_catalog_missing_record_and_revision_tamper(cell):
    setup_artifact(cell)
    with cell.ledger.db:
        cell.ledger.db.execute("UPDATE assurance_meta SET revision=0")
    with pytest.raises(EvidenceError, match="DOMAIN_OR_REVISION"):
        cell.assurance.catalog.census()
    with cell.ledger.db:
        cell.ledger.db.execute("UPDATE assurance_meta SET revision=1")
        cell.ledger.db.execute("DELETE FROM assurance_catalog")
    with pytest.raises(EvidenceError, match="DOMAIN_OR_REVISION"):
        cell.assurance.catalog.verify()
