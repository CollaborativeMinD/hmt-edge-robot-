"""test_resident_analytics: transport interface."""

import asyncio
import json

import httpx
import pytest
from test_resident_analytics_base import HTTP_CLIENT

from hmt_edge_robot.contracts import canonical
from hmt_edge_robot.resident import OpenAICompatibleProvider, ResidentHMT


def mock_client(monkeypatch, response):
    def factory(**kwargs):
        return HTTP_CLIENT(transport=httpx.MockTransport(lambda req: response(req)), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)

def test_http_adapter_canary_proposal_usage(cell, monkeypatch):
    def respond(req):
        body = json.loads(req.content)
        assert body["max_tokens"] == 512
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "model": "fixture-v1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": canonical(
                                {"action": "inspect", "explanation": "ok", "evidence_refs": []}
                            )
                        },
                    }
                ],
            },
        )

    mock_client(monkeypatch, respond)
    provider = OpenAICompatibleProvider("http://localhost:8080/v1", "fixture-v1", cell.policy)
    context = cell.resident.context(cell.status())
    assert len(asyncio.run(provider.qualify(context))) == 64
    resident = ResidentHMT(cell.policy, cell.ledger, provider)
    assert asyncio.run(resident.ask(cell.status(), "inspect")).decision == "ADMIT"
    assert provider.usage[-1]["completion_tokens"] == 10

@pytest.mark.parametrize("payload", [{"model": "wrong"}, {"model": "fixture-v1", "choices": []}])
def test_http_invalid_response(cell, monkeypatch, payload):
    mock_client(monkeypatch, lambda req: httpx.Response(200, json=payload))
    provider = OpenAICompatibleProvider("http://localhost/v1", "fixture-v1", cell.policy)
    provider.qualified = True
    assert (
        asyncio.run(
            ResidentHMT(cell.policy, cell.ledger, provider).ask(cell.status(), "inspect")
        ).decision
        == "HOLD"
    )
