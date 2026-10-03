"""test_assurance_integration: http interface."""




from conftest import TOKEN
from fastapi.testclient import TestClient
from test_assurance_readiness_effects import effect_contract, effect_trace, spec, trace

from hmt_edge_robot.api import create_app


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
