"""test_api_cli: http interface."""





import pytest
from conftest import TOKEN, request
from fastapi.testclient import TestClient
from test_api_cli_base import API_TOKEN, HEADERS

from hmt_edge_robot.api import create_app
from hmt_edge_robot.ledger import EvidenceError
from hmt_edge_robot.runtime import RobotCell


def test_api_full_operator_flow(cell):
    client = TestClient(create_app(cell, API_TOKEN))
    assert client.get("/health").json()["mode"] == "SIL"
    assert client.get("/status").status_code == 401
    assert (
        client.post(
            "/sessions", headers=HEADERS, json={"operator_id": "operator", "proof": "wrong"}
        ).status_code
        == 403
    )
    session = client.post(
        "/sessions", headers=HEADERS, json={"operator_id": "operator", "proof": TOKEN}
    ).json()["session_id"]
    body = {"operator_id": "operator", "session_id": session}
    assert client.post("/simulation/observe", headers=HEADERS).status_code == 200
    assert client.get("/status", headers=HEADERS).json()["substrate_ready"]
    order = request(cell, session).model_dump(mode="json")
    assert client.post("/tasks", headers=HEADERS, json=order).json()["state"] == "PLANNED"
    assert client.post("/cycle", headers=HEADERS).json()["state"] == "SUCCEEDED"
    assert client.get("/analytics", headers=HEADERS).json()["sensor_trends"]["sample_count"] == 1
    result = client.post("/resident", headers=HEADERS, json={**body, "question": "inspect"})
    assert result.json()["receipt"]["decision"] == "ADMIT"
    assert result.json()["tool_result"]["substrate_ready"]
    assert client.post("/sessions/heartbeat", headers=HEADERS, json=body).json()["accepted"]
    assert client.post("/stop", headers=HEADERS).json()["stopped"]
    assert client.post("/reset", headers=HEADERS, json=body).json()["accepted"]
    assert client.post("/sessions/revoke", headers=HEADERS, json=body).json()["accepted"]
    assert (
        client.post("/resident", headers=HEADERS, json={**body, "question": "inspect"}).status_code
        == 403
    )
    assert client.post("/sessions/revoke", headers=HEADERS, json=body).status_code == 403

def test_api_cancel_errors_and_strict_payload(cell, ready, monkeypatch):
    client = TestClient(create_app(cell, API_TOKEN))
    body = {"operator_id": "operator", "session_id": ready}
    cell.orchestrator.submit(request(cell, ready))
    assert (
        client.post("/tasks/task-1/cancel", headers=HEADERS, json=body).json()["state"]
        == "CANCELLED"
    )
    assert client.post("/tasks/task-1/cancel", headers=HEADERS, json=body).status_code == 409
    order = request(cell, ready, "invalid").model_dump(mode="json")
    assert client.post("/tasks", headers=HEADERS, json={**order, "bypass": True}).status_code == 422
    assert client.post("/tasks", headers=HEADERS, json=order).status_code == 200
    assert client.post("/tasks", headers=HEADERS, json=order).status_code == 503
    assert cell.driver.stopped
    with pytest.raises(ValueError):
        create_app(cell, "short")

def test_api_lifespan_closes(tmp_path):
    cell = RobotCell(tmp_path / "db", TOKEN)
    with TestClient(create_app(cell, API_TOKEN)) as client:
        assert client.get("/health").status_code == 200
    with pytest.raises(EvidenceError):
        cell.ledger.append("test", "1", "event", {})
