"""Mission readiness traces and empirical recovery envelopes; no hardware readiness claim."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import numpy as np

from ..contracts import digest
from .contracts import AssuranceReport, RecoverySpec, RecoveryTrace, StageObservation
from .kernel import AssuranceKernel, witnessed


class MissionColdStartCartographer:
    def __init__(self, kernel: AssuranceKernel):
        self.kernel = kernel

    @witnessed
    def assess(self, spec: RecoverySpec, trace: RecoveryTrace) -> AssuranceReport:
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

    def _verdict(self, spec, trace, ready, ordered, elapsed):
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

    async def collect(
        self,
        spec: RecoverySpec,
        probe: Callable[[str], Awaitable[StageObservation]],
        collector_id: str = "software-probe",
    ) -> RecoveryTrace:
        started = self.kernel.clock()
        epochs = self.kernel.epochs()
        self.kernel.ledger.append(
            "assurance",
            spec.capability_id,
            "recovery_probe_intent",
            {"spec": spec.model_dump(mode="json"), "epochs": epochs.model_dump(mode="json")},
        )
        try:
            observations = await self._collect_stages(spec, probe, started)
        except Exception as exc:
            self.kernel.alert("MCC", "PROBE_FAILED", type(exc).__name__)
            raise
        trace = RecoveryTrace(
            origin="SOFTWARE_COLLECTED",
            collector_id=collector_id,
            epochs=epochs,
            started_at=started,
            observations=tuple(observations),
        )
        self.kernel.ledger.append(
            "assurance", spec.capability_id, "recovery_trace", trace.model_dump(mode="json")
        )
        return trace

    async def _collect_stages(self, spec, probe, started):
        observations = []
        try:
            for stage in spec.stages:
                remaining = spec.recovery_horizon_sec - (self.kernel.clock() - started)
                if remaining <= 0:
                    observations.append(
                        StageObservation(
                            stage=stage, elapsed_sec=self.kernel.clock() - started, succeeded=False
                        )
                    )
                    break
                result = await asyncio.wait_for(probe(stage), remaining)
                result = StageObservation.model_validate(result)
                if result.stage != stage:
                    raise ValueError("PROBE_STAGE_MISMATCH")
                observations.append(
                    StageObservation(
                        stage=stage,
                        elapsed_sec=self.kernel.clock() - started,
                        succeeded=result.succeeded,
                        transaction_hash=result.transaction_hash,
                    )
                )
                if not result.succeeded:
                    break
        except TimeoutError:
            observations.append(
                StageObservation(
                    stage=stage, elapsed_sec=self.kernel.clock() - started, succeeded=False
                )
            )
        return observations

    def envelope(self, spec: RecoverySpec, traces: tuple[RecoveryTrace, ...]) -> dict:
        if not 1 <= len(traces) <= 256:
            raise ValueError("CAMPAIGN_SIZE_INVALID")
        reports = [self.assess(spec, trace) for trace in traces]
        times = np.array([dict(r.report.metrics)["mission_ready_sec"] for r in reports])
        failures = sum(r.report.verdict != "MISSION_READY" for r in reports)
        # Wilson 95% upper confidence endpoint on observed failure proportion.
        n, z = len(times), 1.959963984540054
        p = failures / n
        upper = (p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (
            1 + z * z / n
        )
        return {
            "classification": "EMPIRICAL_SOFTWARE_CAMPAIGN",
            "sample_count": n,
            "p95_sec": float(np.quantile(times, 0.95, method="higher")),
            "max_sec": float(times.max()),
            "failure_count": failures,
            "failure_probability_upper_95": float(upper),
            "report_hashes": [r.report_hash for r in reports],
            "scenario": spec.scenario,
            "worst_case_guarantee": False,
        }
