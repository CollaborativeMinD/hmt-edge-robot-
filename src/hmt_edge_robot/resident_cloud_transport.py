"""OpenAICompatibleProvider: transport responsibilities on the owning instance."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import httpx

from .contracts import ResidentProposal, canonical, digest

if TYPE_CHECKING:
    from hmt_edge_robot.resident_cloud import OpenAICompatibleProvider

async def _call(self: OpenAICompatibleProvider, context: dict[str, Any], question: str) -> str:
    headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
    body = self._body(context, question)
    if self.budget is not None:
        profiles = {
            ("https://api.openai.com/v1", "gpt-4.1-mini-2025-04-14"),
            ("https://openrouter.ai/api/v1", "openai/gpt-4.1-mini"),
        }
        if (self.base_url, self.model_id) not in profiles:
            raise RuntimeError("BUDGET_PRICE_PROFILE_MISMATCH")
        self.budget.reserve(len(canonical(body).encode()))
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        async with client.stream(
            "POST", self.base_url + "/chat/completions", headers=headers, json=body
        ) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 32768:
                    raise ValueError("MODEL_RESPONSE_TOO_LARGE")
    return self._decode(bytes(data))

async def qualify(self: OpenAICompatibleProvider, context: dict[str, Any]) -> str:
    """L4 canary: bind actual schema-compliant response to the live profile."""
    self.qualified = False
    raw = await asyncio.wait_for(self._call(context, "Inspect current status."), timeout=6)
    proposal = ResidentProposal.model_validate_json(raw)
    available = {r["determinism_hash"] for r in context["evidence"]}
    if any(ref not in available for ref in proposal.evidence_refs):
        raise ValueError("MODEL_EVIDENCE_INVALID")
    self.qualified = True
    return digest(
        {
            "model_id": self.model_id,
            "policy_epoch": self.policy_epoch,
            "schema": ResidentProposal.model_json_schema(),
            "response": proposal.model_dump(mode="json"),
        }
    )
