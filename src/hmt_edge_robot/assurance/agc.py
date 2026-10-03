"""Dependency closure and fenced catalog reclamation with durable evidence before commit."""

from __future__ import annotations

from typing import Callable

from ..contracts import digest
from .agc_admission import _admit
from .agc_mutation import _execute, _transition
from .agc_planning import _decision, _decisions
from .catalog import ArtifactCatalog
from .contracts import Census, MutationGrant, ReclamationPlan
from .kernel import AssuranceKernel


class AutonomyGarbageCollector:
    def __init__(
        self,
        kernel: AssuranceKernel,
        catalog: ArtifactCatalog,
        authorize: Callable[[MutationGrant], bool] = lambda _: False,
        dwell_sec: float = 60.0,
    ):
        if type(dwell_sec) is not float or not 0 <= dwell_sec <= 86400:
            raise ValueError("QUARANTINE_DWELL_INVALID")
        self.kernel, self.catalog, self.authorize, self.dwell_sec = (
            kernel,
            catalog,
            authorize,
            dwell_sec,
        )

    def plan(self, census: Census) -> ReclamationPlan:
        try:
            return self._plan(census)
        except Exception as exc:
            self.kernel.alert("AGC", "PLANNING_FAILED", type(exc).__name__)
            raise

    def _plan(self, census: Census) -> ReclamationPlan:
        decisions = self._decisions(census)
        for report in decisions:
            self.kernel.seal(report)
        plan = ReclamationPlan(
            census_hash=digest(census.model_dump(mode="json")),
            revision=census.revision,
            epochs=census.epochs,
            expires_at=census.expires_at,
            decisions=decisions,
        )
        self.kernel.ledger.append(
            "assurance",
            digest(plan.model_dump(mode="json")),
            "reclamation_plan",
            plan.model_dump(mode="json"),
        )
        return plan

    _decisions = _decisions

    _decision = _decision

    def execute(self, plan: ReclamationPlan, grant: MutationGrant):
        try:
            return self._execute(plan, grant)
        except Exception as exc:
            self.kernel.alert("AGC", "MUTATION_DENIED_OR_FAILED", type(exc).__name__)
            raise

    _execute = _execute

    _admit = _admit

    _transition = _transition
