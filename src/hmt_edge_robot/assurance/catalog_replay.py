"""ArtifactCatalog: replay responsibilities on the owning instance."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from ..ledger import EvidenceError
from .catalog_storage import storage_guard as storage_guard
from .contracts import (
    ArtifactRecord,
)

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.catalog import ArtifactCatalog

@storage_guard
def verify(self: ArtifactCatalog) -> int:
    self.ledger.verify()
    with self.ledger.lock:
        self._verify_domain()
        rows = self.ledger.db.execute("SELECT * FROM assurance_catalog ORDER BY artifact_id")
        count = 0
        for row in rows:
            count += 1
            record = ArtifactRecord.model_validate_json(row[1])
            if row[0] != record.identity.artifact_id or row[3] not in {
                "ACTIVE",
                "QUARANTINE",
                "RECLAIMED",
            }:
                raise EvidenceError("CATALOG_PROJECTION_MISMATCH")
            if row[3] != "RECLAIMED" and (
                row[2] is None
                or hashlib.sha256(row[2]).hexdigest() != record.identity.identity_hash
            ):
                raise EvidenceError("ARTIFACT_CONTENT_HASH_MISMATCH")
            last = self.ledger.db.execute(
                "SELECT payload FROM events WHERE request_id=? AND packet_type IN ('artifact_registered','artifact_references_changed','artifact_mutated') ORDER BY seq DESC LIMIT 1",
                (row[0],),
            ).fetchone()
            payload = json.loads(last[0]) if last else {}
            expected_record = payload.get("record", payload)
            expected_state = payload.get("state", "ACTIVE")
            if (
                expected_record != record.model_dump(mode="json")
                or expected_state != row[3]
                or payload.get("quarantined_at") != row[4]
                or (row[3] == "RECLAIMED" and row[2] is not None)
            ):
                raise EvidenceError("CATALOG_PROJECTION_MISMATCH")
    return count

def _verify_domain(self: ArtifactCatalog) -> None:
    expected, revision = set(), 0
    for kind, request_id in self.ledger.db.execute(
        "SELECT packet_type,request_id FROM events WHERE packet_type IN ('artifact_registered','artifact_references_changed','artifact_mutated') ORDER BY seq"
    ):
        revision += 1
        if kind == "artifact_registered":
            expected.add(request_id)
    actual = {r[0] for r in self.ledger.db.execute("SELECT artifact_id FROM assurance_catalog")}
    row = self.ledger.db.execute("SELECT revision FROM assurance_meta").fetchone()
    if actual != expected or row != (revision,):
        raise EvidenceError("CATALOG_DOMAIN_OR_REVISION_MISMATCH")
