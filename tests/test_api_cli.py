import argparse
import json
import secrets
import sys

import pytest
from conftest import TOKEN, request
from fastapi.testclient import TestClient

from hmt_edge_robot.api import create_app
from hmt_edge_robot.cli import demonstrate, dispatch, main, parser, serve
from hmt_edge_robot.contracts import Policy
from hmt_edge_robot.ledger import EvidenceError
from hmt_edge_robot.runtime import RobotCell

API_TOKEN = secrets.token_hex(24)
HEADERS = {"Authorization": "Bearer " + API_TOKEN}


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


def test_cli_demo_and_commands(cell, tmp_path, capsys):
    result = demonstrate(cell, TOKEN)
    assert result["outcome"]["state"] == "SUCCEEDED"
    assert result["resident"]["decision"] == "ADMIT"
    assert result["health_model"]["decision"] == "HOLD"
    for command in ("replay", "analytics", "export", "resident"):
        args = argparse.Namespace(
            command=command, output=tmp_path / "out.parquet", question="inspect"
        )
        dispatch(args, cell, TOKEN)
        assert json.loads(capsys.readouterr().out)
    assert (tmp_path / "out.parquet").exists()
    assert parser().parse_args(["demo"]).command == "demo"


def test_cli_entry_and_serve_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["hmt-edge-robot", "demo", "--database", str(tmp_path / "demo.db")]
    )
    main()
    assert json.loads(capsys.readouterr().out)["mode"] == "SIL"
    monkeypatch.setattr(sys, "argv", ["hmt-edge-robot", "resident"])
    monkeypatch.delenv("HMT_OPERATOR_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main()
    monkeypatch.setenv("HMT_OPERATOR_TOKEN", TOKEN)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hmt-edge-robot",
            "demo",
            "--model-id",
            "missing",
            "--database",
            str(tmp_path / "missing.db"),
        ],
    )
    with pytest.raises(SystemExit):
        main()
    import uvicorn

    called = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: called.append(options))
    cell = RobotCell(tmp_path / "serve.db", TOKEN)
    args = argparse.Namespace(port=8080, command="serve")
    monkeypatch.delenv("HMT_API_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        serve(args, cell)
    monkeypatch.setenv("HMT_API_TOKEN", API_TOKEN)
    dispatch(args, cell, TOKEN)
    assert called[0]["host"] == "127.0.0.1" and called[0]["workers"] == 1
    cell.close()


def test_cli_qualified_model_seam(tmp_path, monkeypatch, capsys):
    from hmt_edge_robot.resident import OpenAICompatibleProvider

    async def qualification(self, context):
        self.qualified = True
        return "0" * 64

    async def proposal(self, context, question):
        return '{"action":"inspect","explanation":"ok","evidence_refs":[]}'

    monkeypatch.setattr(OpenAICompatibleProvider, "qualify", qualification)
    monkeypatch.setattr(OpenAICompatibleProvider, "propose", proposal)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(Policy().model_dump_json())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hmt-edge-robot",
            "demo",
            "--model-url",
            "http://localhost/v1",
            "--model-id",
            "fixture-v1",
            "--policy",
            str(policy_path),
            "--database",
            str(tmp_path / "model.db"),
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["resident"]["model_id"] == "fixture-v1"


def test_operator_token_minimum(tmp_path):
    with pytest.raises(ValueError):
        RobotCell(tmp_path / "db", "short")
