"""AutonomyGarbageCollector: planning responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import digest
from .contracts import AssuranceReport, Census, WitnessScope

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.agc import AutonomyGarbageCollector

def _decisions(self: AutonomyGarbageCollector, census: Census) -> tuple[AssuranceReport, ...]:
    records = {r.identity.artifact_id: r for r in census.records}
    unknown = (
        not census.complete
        or census.epochs != self.kernel.epochs()
        or not census.observed_at <= self.kernel.clock() < census.expires_at
        or any(
            r.epochs != census.epochs or set(r.dependencies) - records.keys()
            for r in records.values()
        )
    )
    protected = {}
    for key, r in records.items():
        if r.authority_refs:
            protected[key] = "LIVE"
        elif r.recovery_refs or r.cold_start_refs:
            protected[key] = "RECOVERY_REQUIRED"
        elif r.evidence_refs or r.side_effect_refs:
            protected[key] = "EVIDENCE_REQUIRED"
    frontier = sorted(protected)
    while frontier:
        key = frontier.pop()
        for dependency in records[key].dependencies:
            if dependency in records and dependency not in protected:
                protected[dependency] = protected[key]
                frontier.append(dependency)
    census_hash = digest(census.model_dump(mode="json"))
    return tuple(
        self._decision(
            r,
            census,
            "UNKNOWN_HOLD" if unknown else protected.get(key, "SAFE_TO_RECLAIM"),
            census_hash,
        )
        for key, r in sorted(records.items())
    )

def _decision(self: AutonomyGarbageCollector, record, census, verdict, census_hash):
    scope = WitnessScope(
        subject_id=record.identity.artifact_id,
        subject_hash=record.identity.identity_hash,
        contract_hash=census_hash,
        collector_id="managed-catalog",
        epochs=self.kernel.epochs(),
        observed_at=census.observed_at,
        expires_at=census.expires_at,
        coverage=("authority", "recovery", "evidence", "effects", "dependency_closure"),
    )
    if verdict == "SAFE_TO_RECLAIM":
        with self.kernel.ledger.lock:
            row = self.kernel.ledger.db.execute(
                "SELECT state FROM assurance_catalog WHERE artifact_id=?",
                (record.identity.artifact_id,),
            ).fetchone()
        if row and row[0] == "QUARANTINE":
            verdict = "QUARANTINE"
    return AssuranceReport(
        component="AGC",
        scope=scope,
        verdict=verdict,
        reason_codes=("AGC_" + verdict,),
        observation_hash=digest(record.model_dump(mode="json")),
        artifact_refs=record.dependencies,
    )
