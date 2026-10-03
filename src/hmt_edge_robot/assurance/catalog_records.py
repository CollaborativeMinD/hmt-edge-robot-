"""ArtifactCatalog: records responsibilities on the owning instance."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from ..contracts import utc_now
from .catalog_storage import storage_guard as storage_guard
from .contracts import (
    ArtifactIdentity,
    ArtifactRecord,
)

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.catalog import ArtifactCatalog

@storage_guard
def put(
    self: ArtifactCatalog,
    artifact_id: str,
    content: bytes,
    owner: str = "managed_catalog",
    artifact_type: str = "software_blob",
) -> ArtifactRecord:
    if type(content) is not bytes or len(content) > 16_777_216:
        raise ValueError("ARTIFACT_CONTENT_BOUND_EXCEEDED")
    record = ArtifactRecord(
        identity=ArtifactIdentity(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            owner_surface=owner,
            generation=1,
            size_bytes=len(content),
            identity_hash=hashlib.sha256(content).hexdigest(),
            created_at_utc=utc_now(),
        ),
        epochs=self.epochs(),
    )
    with self.ledger.lock, self.ledger.db:
        self.ledger.db.execute("BEGIN IMMEDIATE")
        if (
            self.ledger.db.execute("SELECT count(*) FROM assurance_catalog").fetchone()[0]
            >= 1024
        ):
            raise ValueError("CATALOG_CAPACITY_EXCEEDED")
        if self.ledger.db.execute(
            "SELECT 1 FROM assurance_catalog WHERE artifact_id=?", (artifact_id,)
        ).fetchone():
            raise ValueError("ARTIFACT_ALREADY_REGISTERED")
        self.ledger.db.execute(
            "INSERT INTO assurance_catalog VALUES(?,?,?,'ACTIVE',NULL)",
            (artifact_id, record.model_dump_json(), content),
        )
        self._changed("artifact_registered", record)
    return record

@storage_guard
def update(self: ArtifactCatalog, record: ArtifactRecord) -> None:
    with self.ledger.lock, self.ledger.db:
        self.ledger.db.execute("BEGIN IMMEDIATE")
        row = self._row(record.identity.artifact_id)
        previous = ArtifactRecord.model_validate_json(row[1])
        if previous.identity != record.identity or row[3] == "RECLAIMED":
            raise ValueError("ARTIFACT_IDENTITY_IMMUTABLE")
        self.ledger.db.execute(
            "UPDATE assurance_catalog SET record=? WHERE artifact_id=?",
            (record.model_dump_json(), record.identity.artifact_id),
        )
        self._changed("artifact_references_changed", record)

def _changed(self: ArtifactCatalog, kind: str, record: ArtifactRecord) -> None:
    self.ledger.db.execute("UPDATE assurance_meta SET revision=revision+1")
    row = self._row(record.identity.artifact_id)
    self.ledger._append(
        "assurance",
        record.identity.artifact_id,
        kind,
        {"record": record.model_dump(mode="json"), "state": row[3], "quarantined_at": row[4]},
    )

def _row(self: ArtifactCatalog, artifact_id: str):
    row = self.ledger.db.execute(
        "SELECT * FROM assurance_catalog WHERE artifact_id=?", (artifact_id,)
    ).fetchone()
    if row is None:
        raise ValueError("ARTIFACT_NOT_FOUND")
    return row
