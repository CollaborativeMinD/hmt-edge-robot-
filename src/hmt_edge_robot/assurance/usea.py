"""Compatibility facade for the decomposed usea interfaces."""

from __future__ import annotations

from ..contracts import digest
from .contracts import AssuranceReport, EffectContract, EffectTrace
from .kernel import AssuranceKernel, witnessed
from .usea_manifest import file_manifest as file_manifest
from .usea_manifest import manifest_effects as manifest_effects


class UndeclaredSideEffectAttestor:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    @witnessed
    def attest(self, contract: EffectContract, trace: EffectTrace) -> AssuranceReport:
        allowed = {(e.kind, e.target) for e in contract.allowed}
        violations = [e for e in trace.observed if (e.kind, e.target) not in allowed]
        scope = self.kernel.scope(
            contract.executable_id,
            contract.executable_hash,
            contract,
            trace.collector_id,
            trace.started_at,
            contract.witness_ttl_sec,
            tuple(trace.coverage),
        )
        reasons = tuple(sorted({"UNDECLARED_" + e.kind.upper() + "_ACCESS" for e in violations}))
        if (
            violations
            or trace.runtime_sec > contract.max_runtime_sec
            or trace.exit_code not in contract.allowed_exit_codes
        ):
            verdict = "SIDE_EFFECT_OUTSIDE_CONTRACT"
            reasons += ("EXECUTION_BOUNDARY_VIOLATION",)
        elif (
            trace.origin != "SOFTWARE_COLLECTED"
            or not trace.complete
            or not set(contract.required_coverage).issubset(trace.coverage)
            or trace.executable_hash != contract.executable_hash
            or trace.epochs != scope.epochs
            or not self.kernel.valid(scope)
        ):
            verdict, reasons = (
                "ATTESTATION_INCOMPLETE",
                ("COVERAGE_IDENTITY_OR_FRESHNESS_INCOMPLETE",),
            )
        else:
            verdict, reasons = (
                "DECLARED_EFFECT_CONFIRMED",
                ("EFFECTS_CONFORM_WITHIN_DECLARED_COVERAGE",),
            )
        return AssuranceReport(
            component="USEA",
            scope=scope,
            verdict=verdict,
            reason_codes=reasons,
            artifact_refs=trace.artifact_refs,
            observation_hash=digest(trace.model_dump(mode="json")),
            metrics=(
                ("runtime_sec", trace.runtime_sec),
                ("observed_effect_count", float(len(trace.observed))),
            ),
        )
