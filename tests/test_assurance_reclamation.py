"""Compatibility facade for the decomposed test_assurance_reclamation interfaces."""

import pytest
from conftest import TOKEN
from test_assurance_reclamation_base import grant as grant
from test_assurance_reclamation_base import plan as plan
from test_assurance_reclamation_base import setup_artifact as setup_artifact


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
