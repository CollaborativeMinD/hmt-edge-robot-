"""test_resident_analytics: budget interface."""

import asyncio

import httpx
import pytest
from test_resident_analytics_transport import mock_client

from hmt_edge_robot.contracts import Policy
from hmt_edge_robot.resident import CallBudget, OpenAICompatibleProvider, ResidentHMT


@pytest.mark.parametrize(
    "changes",
    [
        {"finish_reason": "length"},
        {"refusal": "denied"},
        {"usage": {}},
        {"usage": {"prompt_tokens": True, "completion_tokens": 1}},
        {"usage": {"prompt_tokens": 1, "completion_tokens": -1}},
    ],
)
def test_paid_adapter_incomplete_or_uncertain_usage_holds(cell, monkeypatch, changes):
    choice = {
        "finish_reason": changes.get("finish_reason", "stop"),
        "message": {
            "content": '{"action":"inspect","explanation":"ok","evidence_refs":[]}',
            "refusal": changes.get("refusal"),
        },
    }
    payload = {
        "model": "gpt-4.1-mini-2025-04-14",
        "choices": [choice],
        "usage": changes.get("usage", {"prompt_tokens": 100, "completion_tokens": 10}),
    }
    mock_client(monkeypatch, lambda req: httpx.Response(200, json=payload))
    budget = CallBudget()
    provider = OpenAICompatibleProvider(
        "https://api.openai.com/v1", payload["model"], Policy(allow_cloud=True), budget=budget
    )
    with pytest.raises(ValueError):
        asyncio.run(provider.qualify(cell.resident.context(cell.status())))
    assert not provider.qualified and budget.calls == 1 and budget.reserved_usd > 0

def test_http_size_status_and_evidence_guards(cell, monkeypatch):
    mock_client(monkeypatch, lambda req: httpx.Response(200, content=b"x" * 32769))
    provider = OpenAICompatibleProvider("http://localhost/v1", "fixture-v1", cell.policy)
    provider.qualified = True
    assert (
        asyncio.run(
            ResidentHMT(cell.policy, cell.ledger, provider).ask(cell.status(), "inspect")
        ).decision
        == "HOLD"
    )
    mock_client(monkeypatch, lambda req: httpx.Response(429))
    assert (
        asyncio.run(
            ResidentHMT(cell.policy, cell.ledger, provider).ask(cell.status(), "inspect")
        ).decision
        == "HOLD"
    )
    mock_client(
        monkeypatch,
        lambda req: httpx.Response(
            200,
            json={
                "model": "fixture-v1",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"action":"inspect","explanation":"ok","evidence_refs":["fake"]}'
                        },
                    }
                ],
            },
        ),
    )
    with pytest.raises(ValueError):
        asyncio.run(provider.qualify(cell.resident.context(cell.status())))
    budgeted = OpenAICompatibleProvider(
        "http://localhost/v1", "fixture-v1", cell.policy, budget=CallBudget()
    )
    with pytest.raises(RuntimeError):
        asyncio.run(budgeted._call(cell.resident.context(cell.status()), "inspect"))
