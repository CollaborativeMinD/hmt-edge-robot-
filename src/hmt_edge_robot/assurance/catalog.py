"""Compatibility facade for the decomposed catalog interfaces."""

from __future__ import annotations

from typing import Callable

from ..ledger import Ledger
from .catalog_authority import census, issue, read
from .catalog_records import _changed, _row, put, update
from .catalog_replay import _verify_domain, verify
from .catalog_storage import storage_guard as storage_guard
from .contracts import (
    Epochs,
)


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

    put = put

    update = update

    _changed = _changed

    _row = _row

    census = census

    issue = issue

    verify = verify

    _verify_domain = _verify_domain

    read = read
