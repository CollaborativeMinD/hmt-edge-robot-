"""Compatibility facade for the decomposed test_assurance_integration interfaces."""

import json

import polars as pl
import pytest
from conftest import TOKEN
from test_assurance_integration_http import client_for as client_for
from test_assurance_readiness_effects import effect_contract, effect_trace, spec, trace

from hmt_edge_robot.contracts import digest
from hmt_edge_robot.runtime import RobotCell


def test_cross_component_witness_retention(cell, ready):
    cell.assurance.catalog.put("model", b"weights")
    s = spec(artifact_refs=("model",))
    report = cell.assurance.mcc.assess(s, trace(cell, s))
    assert cell.assurance.bind_witness(report, ready, "operator") == 1
    assert cell.assurance.agc.plan(cell.assurance.catalog.census()).decisions[0].verdict == "RECOVERY_REQUIRED"
    cell.assurance.catalog.put("output", b"evidence")
    report = cell.assurance.usea.attest(effect_contract(), effect_trace(artifact_refs=("output",)))
    assert cell.assurance.bind_witness(report, ready, "operator") == 1
    decisions = {d.scope.subject_id:d.verdict for d in cell.assurance.agc.plan(cell.assurance.catalog.census()).decisions}
    assert decisions["output"] == "EVIDENCE_REQUIRED"
    with pytest.raises(PermissionError):
        cell.assurance.bind_witness(report.model_copy(update={"event_hash": digest("forged")}), ready, "operator")
    with pytest.raises(PermissionError):
        cell.assurance.bind_witness(report.model_copy(update={"report_hash": digest("forged")}), ready, "operator")
    with pytest.raises(PermissionError):
        cell.assurance.bind_witness(report, "invalid", "operator")

def test_observer_durable_cursor_ack_and_restart(cell, tmp_path, clock):
    result = cell.assurance.usea.attest(effect_contract(), effect_trace(complete=False))
    notices = cell.assurance.kernel.notices(limit=1)
    assert notices[0]["severity"] == "ALERT" and notices[0]["requires_ack"]
    cell.assurance.kernel.acknowledge(result.report_hash, "operator")
    assert cell.assurance.kernel.notices(after_seq=notices[0]["seq"]) == []
    reopened = RobotCell(cell.ledger.path, TOKEN, clock=clock, read_only=True)
    try:
        assert reopened.assurance.kernel.notices()[0]["report_hash"] == result.report_hash
        assert reopened.assurance.analytics.summary()[0]["count"] == 1
    finally:
        reopened.close()
    with pytest.raises(ValueError):
        cell.assurance.kernel.notices(limit=0)
    with pytest.raises(ValueError):
        cell.assurance.kernel.notices(after_seq=-1)
    with pytest.raises(ValueError):
        cell.assurance.kernel.acknowledge(digest("absent"), "operator")

def test_observer_analysis_failure_not_silent(cell):
    with pytest.raises(AttributeError):
        cell.assurance.usea.attest(None, effect_trace())
    notice = cell.assurance.kernel.notices()[-1]
    assert notice["reason_codes"] == ["ANALYSIS_FAILED"]
    assert notice["severity"] == "ALERT"
    cell.assurance.kernel.acknowledge(notice["report_hash"], "operator")

def test_assurance_export_sql_parquet_jsonl_graphml(cell, tmp_path):
    cell.assurance.catalog.put("model", b"data")
    s = spec()
    cell.assurance.mcc.assess(s, trace(cell, s))
    cell.assurance.usea.attest(effect_contract(), effect_trace())
    census = cell.assurance.catalog.census()
    cell.assurance.agc.plan(census)
    directory = tmp_path/"exports"
    result = cell.assurance.analytics.export(directory, census)
    assert result["records"] == 3 and result["complete_history"] is False
    assert pl.read_parquet(directory/"capability_readiness_atlas.parquet").height == 1
    assert pl.read_parquet(directory/"effect_attestation.parquet").height == 1
    assert len((directory/"effect_attestation.jsonl").read_text().splitlines()) == 1
    assert "model" in (directory/"artifact_reference_graph.graphml").read_text()
    assert json.loads((directory/"export_manifest.json").read_text()) == result["files"]
    assert sum(r["count"] for r in cell.assurance.analytics.summary()) == 3
    with pytest.raises(ValueError):
        cell.assurance.analytics.frame(1025)
