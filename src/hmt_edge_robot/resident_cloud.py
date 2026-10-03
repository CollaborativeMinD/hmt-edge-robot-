"""resident: cloud interface."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import TypeAdapter

from .contracts import ModelIdentifier, Policy
from .resident_cloud_request import _body, _decode
from .resident_cloud_transport import _call, qualify
from .resident_providers import CallBudget


class OpenAICompatibleProvider:
    """Ollama/llama.cpp/LiteLLM compatible HTTP adapter; explicit profile, no defaults."""

    def __init__(
        self,
        base_url: str,
        model_id: str,
        policy: Policy,
        key: str | None = None,
        budget: CallBudget | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        self.local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
        if (
            parsed.scheme not in ("http", "https")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PROVIDER_PROFILE_INVALID")
        if not self.local and (not policy.allow_cloud or parsed.scheme != "https"):
            raise PermissionError("CLOUD_NOT_ADMITTED")
        TypeAdapter(ModelIdentifier).validate_python(model_id, strict=True)
        self.base_url, self.model_id, self.key = base_url.rstrip("/"), model_id, key
        self.policy_epoch, self.qualified = policy.policy_epoch, False
        self.budget = budget
        self.usage: list[dict[str, Any]] = []

    async def propose(self, context: dict[str, Any], question: str) -> str:
        if not self.qualified or context["policy_epoch"] != self.policy_epoch:
            raise RuntimeError("MODEL_NOT_QUALIFIED")
        return await self._call(context, question)

    _body = _body

    _call = _call

    _decode = _decode

    qualify = qualify
