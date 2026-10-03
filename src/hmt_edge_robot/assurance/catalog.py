"""Single-owner transactional artifact domain. No host filesystem deletion authority."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from functools import wraps
from typing import Callable

from ..contracts import digest, utc_now
from ..ledger import EvidenceError, Ledger
from .contracts import (
    ArtifactIdentity,
    ArtifactRecord,
    Census,
    Epochs,
    MutationAction,
    MutationGrant,
)


def storage_guard(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except sqlite3.Error as exc:
            raise EvidenceError("ASSURANCE_STORAGE_UNAVAILABLE") from exc

    return wrapped


class ArtifactCatalog:
    def __init__(
        self,
        ledger: Ledger,
        clock: Callable[[], float],
        epochs: Callable[[], Epochs],
        read_only: bool = False,
    ):
        self.ledger, self.clock, self.epochs = ledger, clock, epochs
        if not read_only:
            with ledger.lock, ledger.db:
                ledger.db.executescript("""
                CREATE TABLE IF NOT EXISTS assurance_catalog (
                    artifact_id TEXT PRIMARY KEY, record TEXT NOT NULL, content BLOB,
                    state TEXT NOT NULL, quarantined_at REAL);
                CREATE TABLE IF NOT EXISTS assurance_meta (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER NOT NULL);
                INSERT OR IGNORE INTO assurance_meta VALUES(1,0);
                CREATE TABLE IF NOT EXISTS assurance_grants (
                    grant_id TEXT PRIMARY KEY, grant_hash TEXT NOT NULL, consumed INTEGER NOT NULL);
                """)

    @storage_guard
    def put(
        self,
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
    def update(self, record: ArtifactRecord) -> None:
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

    def _changed(self, kind: str, record: ArtifactRecord) -> None:
        self.ledger.db.execute("UPDATE assurance_meta SET revision=revision+1")
        row = self._row(record.identity.artifact_id)
        self.ledger._append(
            "assurance",
            record.identity.artifact_id,
            kind,
            {"record": record.model_dump(mode="json"), "state": row[3], "quarantined_at": row[4]},
        )

    def _row(self, artifact_id: str):
        row = self.ledger.db.execute(
            "SELECT * FROM assurance_catalog WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if row is None:
            raise ValueError("ARTIFACT_NOT_FOUND")
        return row

    @storage_guard
    def census(self, ttl_sec: float = 60.0) -> Census:
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
        self,
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
    def verify(self) -> int:
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

    def _verify_domain(self) -> None:
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

    @storage_guard
    def read(self, artifact_id: str) -> bytes:
        """A quarantined or reclaimed blob is unavailable through the managed read seam."""
        with self.ledger.lock, self.ledger.db:
            self.ledger.db.execute("BEGIN")
            self.verify()
            row = self._row(artifact_id)
            if row[3] != "ACTIVE":
                raise PermissionError("ARTIFACT_NOT_ACTIVE")
            return row[2]
