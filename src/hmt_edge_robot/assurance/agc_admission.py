"""AutonomyGarbageCollector: admission responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import digest
from .contracts import Census

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.agc import AutonomyGarbageCollector

def _admit(self: AutonomyGarbageCollector, plan, grant):
    now = self.kernel.clock()
    issued = self.kernel.ledger.db.execute(
        "SELECT grant_hash,consumed FROM assurance_grants WHERE grant_id=?", (grant.grant_id,)
    ).fetchone()
    issued_event = self.kernel.ledger.db.execute(
        "SELECT payload FROM events WHERE request_id=? AND packet_type='mutation_authority_issued'",
        (grant.grant_id,),
    ).fetchone()
    import json

    genuine = issued_event and json.loads(issued_event[0]) == grant.model_dump(mode="json")
    revision = self.kernel.ledger.db.execute("SELECT revision FROM assurance_meta").fetchone()[
        0
    ]
    if (
        not genuine
        or not issued
        or issued != (digest(grant.model_dump(mode="json")), 0)
        or not self.authorize(grant)
        or grant.plan_hash != digest(plan.model_dump(mode="json"))
        or grant.epochs != self.kernel.epochs()
        or plan.epochs != grant.epochs
        or plan.revision != revision
        or grant.revision != revision
        or now >= min(plan.expires_at, grant.expires_at)
    ):
        raise PermissionError("MUTATION_AUTHORITY_OR_FENCE_INVALID")
    # Never accept caller-forged decisions, even with a grant: reconstruct census and decisions.
    rows = self.kernel.ledger.db.execute(
        "SELECT record FROM assurance_catalog WHERE state!='RECLAIMED' ORDER BY artifact_id"
    ).fetchall()
    from .contracts import ArtifactRecord

    census = Census(
        epochs=plan.epochs,
        revision=revision,
        observed_at=plan.decisions[0].scope.observed_at if plan.decisions else now,
        expires_at=plan.expires_at,
        complete=True,
        records=tuple(ArtifactRecord.model_validate_json(r[0]) for r in rows),
    )
    if (
        digest(census.model_dump(mode="json")) != plan.census_hash
        or self._decisions(census) != plan.decisions
    ):
        raise PermissionError("PLAN_RECONSTRUCTION_MISMATCH")
