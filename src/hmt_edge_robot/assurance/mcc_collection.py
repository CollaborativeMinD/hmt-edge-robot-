"""MissionColdStartCartographer: collection responsibilities on the owning instance."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable

from .contracts import RecoverySpec, RecoveryTrace, StageObservation

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.mcc import MissionColdStartCartographer

async def collect(
    self: MissionColdStartCartographer,
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

async def _collect_stages(self: MissionColdStartCartographer, spec, probe, started):
    observations = []
    stage = spec.stages[0]
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
