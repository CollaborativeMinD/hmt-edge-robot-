"""MissionColdStartCartographer: readiness responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import digest
from .contracts import AssuranceReport, RecoverySpec, RecoveryTrace
from .kernel import witnessed

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.mcc import MissionColdStartCartographer

@witnessed
def assess(self: MissionColdStartCartographer, spec: RecoverySpec, trace: RecoveryTrace) -> AssuranceReport:
    observations = trace.observations
    matched = tuple(o.stage for o in observations) == spec.stages
    ordered = all(
        a.elapsed_sec <= b.elapsed_sec for a, b in zip(observations, observations[1:])
    )
    elapsed = observations[-1].elapsed_sec if observations else 0.0
    ready = (
        trace.origin == "SOFTWARE_COLLECTED"
        and matched
        and ordered
        and all(o.succeeded for o in observations)
    )
    ready = ready and elapsed <= self.kernel.clock() - trace.started_at
    ready = ready and observations[-1].transaction_hash == spec.transaction_hash
    verdict, reasons = self._verdict(spec, trace, ready, ordered, elapsed)
    scope = self.kernel.scope(
        spec.capability_id,
        spec.capability_hash,
        spec,
        trace.collector_id,
        trace.started_at,
        spec.witness_ttl_sec,
        tuple(o.stage for o in observations),
    )
    if not self.kernel.valid(scope) or trace.epochs != scope.epochs:
        verdict, reasons = "RECOVERY_PATH_NOT_AFFORDABLE", ("STALE_OR_CHANGED_EPOCH",)
    return AssuranceReport(
        component="MCC",
        scope=scope,
        verdict=verdict,
        reason_codes=reasons,
        artifact_refs=spec.artifact_refs,
        observation_hash=digest(trace.model_dump(mode="json")),
        metrics=(
            ("mission_ready_sec", elapsed),
            ("remaining_horizon_sec", spec.recovery_horizon_sec),
            ("reserve_sec", spec.reserve_sec),
        ),
    )

def _verdict(self: MissionColdStartCartographer, spec, trace, ready, ordered, elapsed):
    if not ordered:
        return "FIRST_TRANSACTION_FAILED", ("STAGE_TIMING_NOT_MONOTONIC",)
    for o in trace.observations:
        if not o.succeeded:
            specific = {
                "image_available": "IMAGE_UNAVAILABLE",
                "policy_loaded": "POLICY_LOAD_FAILED",
                "model_loaded": "MODEL_LOAD_EXCEEDS_HORIZON",
            }
            return specific.get(o.stage, "FIRST_TRANSACTION_FAILED"), (
                "READINESS_STAGE_FAILED",
            )
    if not ready:
        return "K8S_READY_BUT_MISSION_NOT_READY", ("VALIDATED_MISSION_TRANSACTION_MISSING",)
    if elapsed + spec.reserve_sec >= spec.recovery_horizon_sec:
        return "RECOVERY_PATH_NOT_AFFORDABLE", ("RECOVERY_HORIZON_EXHAUSTED",)
    return "MISSION_READY", ("BOUNDED_MISSION_TRANSACTION_VALIDATED",)
