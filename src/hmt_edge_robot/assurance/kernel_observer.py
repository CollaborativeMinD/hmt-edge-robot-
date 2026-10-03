"""AssuranceKernel: observer responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import digest

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.kernel import AssuranceKernel

def alert(self: AssuranceKernel, component: str, reason: str, exception_type: str) -> str:
    payload = {
        "component": component,
        "severity": "ALERT",
        "requires_ack": True,
        "reason_codes": [reason],
        "exception_type": exception_type,
    }
    report_hash = digest(payload)
    return self.ledger.append(
        "assurance", report_hash, "assurance_notice", {**payload, "report_hash": report_hash}
    )

def notices(self: AssuranceKernel, after_seq: int = 0, limit: int = 32) -> list[dict]:
    if (
        type(after_seq) is not int
        or after_seq < 0
        or type(limit) is not int
        or not 1 <= limit <= 256
    ):
        raise ValueError("OBSERVER_WINDOW_INVALID")
    self.ledger.verify()
    with self.ledger.lock:
        seqs = self.ledger.db.execute(
            "SELECT seq,payload FROM events WHERE seq>? AND packet_type='assurance_notice' ORDER BY seq LIMIT ?",
            (after_seq, limit),
        ).fetchall()
    import json

    return [{"seq": seq, **json.loads(payload)} for seq, payload in seqs]

def acknowledge(self: AssuranceKernel, report_hash: str, observer_id: str) -> str:
    # Calling surface must admit observer identity; unknown evidence cannot be acknowledged.
    with self.ledger.lock:
        row = self.ledger.db.execute(
            "SELECT 1 FROM events WHERE request_id=? AND packet_type='assurance_notice'",
            (report_hash,),
        ).fetchone()
    if not row:
        raise ValueError("NOTICE_NOT_FOUND")
    from pydantic import TypeAdapter

    from ..contracts import Identifier

    observer_id = TypeAdapter(Identifier).validate_python(observer_id)
    return self.ledger.append(
        "assurance", report_hash, "assurance_ack", {"observer_id": observer_id}
    )
