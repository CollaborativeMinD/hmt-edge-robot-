"""catalog: storage interface."""

from __future__ import annotations

import sqlite3
from functools import wraps

from ..ledger import EvidenceError


def storage_guard(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except sqlite3.Error as exc:
            raise EvidenceError("ASSURANCE_STORAGE_UNAVAILABLE") from exc

    return wrapped
