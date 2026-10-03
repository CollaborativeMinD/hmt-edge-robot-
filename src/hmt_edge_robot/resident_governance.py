"""resident: governance interface."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
from pydantic import TypeAdapter, ValidationError

from .contracts import ModelIdentifier, Policy, ResidentProposal, ResidentReceipt, digest
from .ledger import Ledger
from .resident_health import HealthModel
from .resident_providers import DeterministicResident, ResidentProvider


class ResidentHMT:
    def __init__(
        self, policy: Policy, ledger: Ledger, provider: ResidentProvider | None = None
    ) -> None:
        self.policy, self.ledger = policy, ledger
        self.provider: ResidentProvider = provider or DeterministicResident()
        TypeAdapter(ModelIdentifier).validate_python(self.provider.model_id, strict=True)
        if not self.provider.local and not policy.allow_cloud:
            raise PermissionError("CLOUD_NOT_ADMITTED")
        self.health_model = HealthModel()
        self.busy = False

    def context(self, state: dict[str, Any]) -> dict[str, Any]:
        self.ledger.verify()
        if set(state) - {"stopped", "queue_size", "pace_lane", "substrate_ready"}:
            raise ValueError("CONTEXT_STATE_FIELDS_REJECTED")
        return {
            "policy_epoch": self.policy.policy_epoch,
            "policy_hash": digest(self.policy.model_dump(mode="json")),
            "label_schema_hash": digest(ResidentProposal.model_json_schema()),
            "model_id": self.provider.model_id,
            "enabled_tools": ["inspect", "diagnose", "plan_grasp"],
            "evidence": self.ledger.recent(16),
            **state,
        }

    async def ask(self, state: dict[str, Any], question: str) -> ResidentReceipt:
        if not isinstance(question, str) or not 1 <= len(question) <= 2048:
            raise ValueError("QUESTION_BOUNDS_INVALID")
        if self.busy:
            raise RuntimeError("RESIDENT_CAPACITY_EXHAUSTED")
        self.busy = True
        try:
            context = self.context(state)
            context_hash = digest(context)
            raw = await asyncio.wait_for(self.provider.propose(context, question), timeout=6)
            if not isinstance(raw, str) or len(raw.encode()) > 32768:
                raise ValueError("MODEL_RESPONSE_INVALID")
            proposal = ResidentProposal.model_validate_json(raw)
            available = {r["determinism_hash"] for r in context["evidence"]}
            if any(ref not in available for ref in proposal.evidence_refs):
                raise ValueError("MODEL_EVIDENCE_INVALID")
            if context["stopped"] and proposal.action != "hold":
                raise ValueError("STOP_MODEL_PROPOSAL_REJECTED")
            return self._record(context_hash, proposal, "ADMIT", "PROPOSAL_VALIDATED")
        except (
            ValidationError,
            ValueError,
            RuntimeError,
            TimeoutError,
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            context_hash = locals().get("context_hash", "CONTEXT_UNAVAILABLE")
            return self._record(context_hash, None, "HOLD", type(exc).__name__)
        finally:
            self.busy = False

    def _record(
        self, context_hash: str, proposal: ResidentProposal | None, decision: Literal["ADMIT", "HOLD", "DENY"], reason: str
    ) -> ResidentReceipt:
        receipt = ResidentReceipt(
            decision=decision,
            proposal=proposal,
            model_id=self.provider.model_id,
            context_hash=context_hash,
            rejection_reason=reason,
            evidence_id="PENDING",
        )
        payload = receipt.model_dump(mode="json", exclude={"evidence_id"})
        evidence = self.ledger.append("resident", context_hash, "resident_decision", payload)
        return receipt.model_copy(update={"evidence_id": evidence})
