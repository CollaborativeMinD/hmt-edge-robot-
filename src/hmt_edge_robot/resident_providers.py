"""resident: providers interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .contracts import canonical


class ResidentProvider(Protocol):
    model_id: str
    local: bool

    async def propose(self, context: dict[str, Any], question: str) -> str: ...

@runtime_checkable
class QualifiedResidentProvider(Protocol):
    qualified: bool

class CallBudget:
    """Reserve full worst-case cost before every attempt; no retry refund."""

    def __init__(self, limit_usd: float = 1.0, max_calls: int = 4) -> None:
        if not 0 < limit_usd <= 1.0 or not 1 <= max_calls <= 4:
            raise ValueError("BUDGET_INVALID")
        self.limit_usd, self.max_calls = limit_usd, max_calls
        self.reserved_usd, self.calls = 0.0, 0

    def reserve(self, input_bytes: int) -> float:
        # Upper bound: bytes + 2048 protocol tokens, 512 output tokens.
        # GPT-4.1 mini: $0.40/$1.60 per million input/output tokens.
        cost = ((input_bytes + 2048) * 0.4 + 512 * 1.6) / 1_000_000
        if (
            input_bytes > 32768
            or self.calls >= self.max_calls
            or self.reserved_usd + cost > self.limit_usd
        ):
            raise RuntimeError("CALL_BUDGET_EXHAUSTED")
        self.calls += 1
        self.reserved_usd += cost
        return cost

class DeterministicResident:
    """Executable offline resident baseline; explicitly not an LLM."""

    model_id, local = "deterministic-resident-v1", True

    async def propose(self, context: dict[str, Any], question: str) -> str:
        action = (
            "hold"
            if context["stopped"]
            else "diagnose"
            if "fault" in question.lower()
            else "plan_grasp"
            if "grasp" in question.lower()
            else "inspect"
        )
        return canonical(
            {
                "action": action,
                "explanation": f"Policy {context['policy_epoch']}; evidence window contains {len(context['evidence'])} records. Use admitted tools for further inspection.",
                "evidence_refs": [r["determinism_hash"] for r in context["evidence"][-4:]],
            }
        )
