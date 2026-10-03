"""test_assurance_reclamation: authority interface."""

import pytest
from conftest import TOKEN
from test_assurance_reclamation_base import grant, plan, setup_artifact

from hmt_edge_robot.contracts import Policy, digest


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
