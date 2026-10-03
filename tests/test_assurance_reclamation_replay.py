"""test_assurance_reclamation: replay interface."""

import pytest
from test_assurance_reclamation_base import grant, plan, setup_artifact

from hmt_edge_robot.ledger import EvidenceError


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
