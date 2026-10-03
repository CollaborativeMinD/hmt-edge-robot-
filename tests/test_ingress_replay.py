import asyncio

import pytest
from conftest import TOKEN
from fastapi.testclient import TestClient

from hmt_edge_robot.api import create_app
from hmt_edge_robot.contracts import digest
from hmt_edge_robot.ingress import BoundedIngress
from hmt_edge_robot.ledger import EvidenceError, Ledger
from hmt_edge_robot.runtime import RobotCell


def test_global_body_and_rate_bounds(cell):
    client = TestClient(create_app(cell, TOKEN))
    assert client.post("/sessions", content=b"x" * 16385).status_code == 413
    for _ in range(119):
        assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 429


def test_ingress_disconnect_timeout_and_expiry(monkeypatch):
    events = []

    async def app(scope, receive, send):
        events.append(await receive())

    async def send(message):
        events.append(message)

    async def disconnected():
        return {"type": "http.disconnect"}

    async def empty():
        return {"type": "http.request", "body": b"", "more_body": False}

    middleware = BoundedIngress(app, burst=1)
    asyncio.run(middleware({"type": "http"}, disconnected, send))
    assert not events
    middleware.arrivals[0] -= 61
    asyncio.run(middleware({"type": "http"}, empty, send))
    assert events[-1]["type"] == "http.request"
    original = asyncio.wait_for

    async def timeout(awaitable, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", timeout)
    asyncio.run(BoundedIngress(app)({"type": "http"}, empty, send))
    assert events[-2]["status"] == 408
    monkeypatch.setattr(asyncio, "wait_for", original)
    asyncio.run(middleware({"type": "lifespan"}, empty, send))
    assert events[-1]["type"] == "http.request"


def test_read_only_queries_do_not_recover_pending_tasks(tmp_path):
    path = tmp_path / "db"
    ledger = Ledger(path)
    ledger.claim("pending", digest({"x": 1}), {"x": 1})
    ledger.close()
    cell = RobotCell(path, TOKEN, read_only=True)
    task = cell.ledger.task("pending")
    assert task is not None
    assert task["state"] == "PLANNED"
    assert cell.ledger.verify() == 1
    with pytest.raises(EvidenceError):
        cell.ledger.append("test", "1", "event", {})
    cell.close()
    writer = RobotCell(path, TOKEN)
    task = writer.ledger.task("pending")
    assert task is not None
    assert task["state"] == "FAILED"
    writer.close()


def test_projection_tamper_detected(cell, ready):
    from conftest import request

    cell.orchestrator.submit(request(cell, ready))
    cell.ledger.db.execute("UPDATE tasks SET state='SUCCEEDED'")
    with pytest.raises(EvidenceError):
        cell.ledger.verify()
