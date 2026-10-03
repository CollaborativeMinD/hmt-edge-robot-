"""ArtifactCatalog: authority responsibilities on the owning instance."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from ..contracts import digest
from .catalog_storage import storage_guard as storage_guard
from .contracts import (
    ArtifactRecord,
    Census,
    MutationAction,
    MutationGrant,
)

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.catalog import ArtifactCatalog

@storage_guard
def census(self: ArtifactCatalog, ttl_sec: float = 60.0) -> Census:
    if type(ttl_sec) is not float or not 0 < ttl_sec <= 3600:
        raise ValueError("CENSUS_TTL_INVALID")
    with self.ledger.lock, self.ledger.db:
        self.ledger.db.execute("BEGIN")
        self.verify()
        rows = self.ledger.db.execute(
            "SELECT record FROM assurance_catalog WHERE state!='RECLAIMED' ORDER BY artifact_id"
        ).fetchall()
        revision = self.ledger.db.execute("SELECT revision FROM assurance_meta").fetchone()[0]
        now = self.clock()
        return Census(
            epochs=self.epochs(),
            revision=revision,
            observed_at=now,
            expires_at=now + ttl_sec,
            complete=True,
            records=tuple(ArtifactRecord.model_validate_json(r[0]) for r in rows),
        )

@storage_guard
def issue(
    self: ArtifactCatalog,
    plan_hash: str,
    revision: int,
    action: MutationAction,
    artifact_id: str,
    expires_at: float,
    operator_id: str,
    session_id: str,
) -> MutationGrant:
    grant = MutationGrant(
        grant_id="grant-" + secrets.token_hex(16),
        plan_hash=plan_hash,
        epochs=self.epochs(),
        revision=revision,
        action=action,
        artifact_id=artifact_id,
        expires_at=expires_at,
        operator_id=operator_id,
        session_id=session_id,
    )
    with self.ledger.lock, self.ledger.db:
        self.ledger.db.execute(
            "INSERT INTO assurance_grants VALUES(?,?,0)",
            (grant.grant_id, digest(grant.model_dump(mode="json"))),
        )
        self.ledger._append(
            "assurance",
            grant.grant_id,
            "mutation_authority_issued",
            grant.model_dump(mode="json"),
        )
    return grant

@storage_guard
def read(self: ArtifactCatalog, artifact_id: str) -> bytes:
    """A quarantined or reclaimed blob is unavailable through the managed read seam."""
    with self.ledger.lock, self.ledger.db:
        self.ledger.db.execute("BEGIN")
        self.verify()
        row = self._row(artifact_id)
        if row[3] != "ACTIVE":
            raise PermissionError("ARTIFACT_NOT_ACTIVE")
        return row[2]
