"""Triad composition, notifications, data orchestration and private API acceptance."""
import json

import polars as pl
import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient
from test_assurance_readiness_effects import effect_contract, effect_trace, spec, trace

from hmt_edge_robot.api import create_app
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


def test_witness_binding_atomic_unknown_reference(cell, ready):
    cell.assurance.catalog.put("known", b"a")
    report = cell.assurance.usea.attest(effect_contract(), effect_trace(artifact_refs=("known", "missing")))
    revision = cell.assurance.catalog.census().revision
    with pytest.raises(ValueError):
        cell.assurance.bind_witness(report, ready, "operator")
    census = cell.assurance.catalog.census()
    assert census.revision == revision and not census.records[0].side_effect_refs


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


def client_for(cell):
    api_token = TOKEN
    return TestClient(create_app(cell, api_token)), {"Authorization": "Bearer "+api_token}


def test_assurance_api_native_json_and_declared_trace_hold(cell, ready):
    client, headers = client_for(cell)
    s = spec()
    payload = {"session_id":ready, "operator_id":"operator", "spec":s.model_dump(mode="json"),
               "trace":trace(cell,s).model_dump(mode="json")}
    assert client.post("/assurance/readiness", json=payload).status_code == 401
    response = client.post("/assurance/readiness", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["report"]["verdict"] != "MISSION_READY"
    payload["spec"]["recovery_horizon_sec"] = "10"
    assert client.post("/assurance/readiness", json=payload, headers=headers).status_code == 422
    effect = {"session_id":ready, "operator_id":"operator", "contract":effect_contract().model_dump(mode="json"),
              "trace":effect_trace().model_dump(mode="json")}
    response = client.post("/assurance/attest", json=effect, headers=headers)
    assert response.json()["report"]["verdict"] == "ATTESTATION_INCOMPLETE"
    ack = {"session_id":ready, "operator_id":"operator", "report_hash":response.json()["report_hash"]}
    assert client.post("/assurance/ack", json=ack, headers=headers).status_code == 200
    assert len(client.get("/assurance/notices", headers=headers).json()) == 2
    assert client.get("/assurance/analytics", headers=headers).status_code == 200


def test_assurance_api_catalog_and_grant_flow(cell, ready):
    client, headers = client_for(cell)
    context = {"session_id": ready, "operator_id":"operator"}
    response = client.post("/assurance/artifacts", headers=headers, json={**context,"artifact_id":"model","content_base64":"eA=="})
    assert response.status_code == 200
    p = client.post("/assurance/plan", headers=headers, json=context).json()
    g = client.post("/assurance/grant", headers=headers, json={**context, "plan":p,"action":"quarantine","artifact_id":"model"})
    assert g.status_code == 200
    response = client.post("/assurance/execute", headers=headers, json={"plan":p,"grant":g.json()})
    assert response.status_code == 200 and response.json()["report"]["verdict"] == "QUARANTINE"
    response = client.post("/assurance/execute", headers=headers, json={"plan":p,"grant":g.json()})
    assert response.status_code == 403
    assert cell.assurance.catalog.verify() == 1


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


def test_assurance_api_reference_binding_and_scope_rejection(cell, ready):
    client, headers = client_for(cell)
    context = {"session_id":ready, "operator_id":"operator"}
    record = cell.assurance.catalog.put("model", b"weights")
    updated = record.model_copy(update={"evidence_refs": ("audit",)})
    assert client.post("/assurance/references", headers=headers, json={**context,"record":updated.model_dump(mode="json")}).status_code == 200
    s = spec(artifact_refs=("model",))
    sealed = cell.assurance.mcc.assess(s, trace(cell, s))
    assert client.post("/assurance/bind-witness", headers=headers, json={**context,"sealed":sealed.model_dump(mode="json")}).json()["bound_artifacts"] == 1
    bad = {**context,"session_id":"invalid"}
    assert client.post("/assurance/plan", headers=headers, json=bad).status_code == 403
    assert "/assurance/readiness" in client.get("/openapi.json").json()["paths"]


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
