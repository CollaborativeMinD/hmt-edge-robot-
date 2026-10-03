"""Canonical transformation kernel, durable notification outbox and observer decorator."""

from __future__ import annotations

import functools
import math
from typing import Callable

from ..contracts import Contract, digest
from ..ledger import Ledger
from .contracts import AssuranceReport, Epochs, SealedReport, WitnessScope


class AssuranceKernel:
    def __init__(self, ledger: Ledger, clock: Callable[[], float], epochs: Callable[[], Epochs]):
        self.ledger, self.clock, self.epochs = ledger, clock, epochs

    def scope(
        self,
        subject: str,
        identity: str,
        contract: Contract,
        collector: str,
        started: float,
        ttl: float,
        coverage: tuple[str, ...],
    ) -> WitnessScope:
        return WitnessScope(
            subject_id=subject,
            subject_hash=identity,
            contract_hash=digest(contract.model_dump(mode="json")),
            collector_id=collector,
            epochs=self.epochs(),
            observed_at=started,
            expires_at=started + ttl,
            coverage=coverage,
        )

    def valid(self, scope: WitnessScope) -> bool:
        now = self.clock()
        return (
            math.isfinite(now)
            and scope.observed_at <= now < scope.expires_at
            and scope.epochs == self.epochs()
        )

    def seal(self, report: AssuranceReport) -> SealedReport:
        payload = report.model_dump(mode="json")
        report_hash = digest(payload)
        alert = report.verdict not in {
            "MISSION_READY",
            "DECLARED_EFFECT_CONFIRMED",
            "SAFE_TO_RECLAIM",
            "RESTORED",
            "RECLAIMED",
        }
        event_hash = self.ledger.append(
            "assurance",
            report_hash,
            "assurance_notice",
            {
                "report": payload,
                "report_hash": report_hash,
                "severity": "ALERT" if alert else "NOTICE",
                "requires_ack": alert,
            },
        )
        return SealedReport(report=report, report_hash=report_hash, event_hash=event_hash)

    def alert(self, component: str, reason: str, exception_type: str) -> str:
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

    def notices(self, after_seq: int = 0, limit: int = 32) -> list[dict]:
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

    def acknowledge(self, report_hash: str, observer_id: str) -> str:
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


def witnessed(method):
    """Persist and notify exactly once for each successful analysis; failures alert and propagate."""

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            report = method(self, *args, **kwargs)
        except Exception as exc:
            self.kernel.alert(type(self).__name__, "ANALYSIS_FAILED", type(exc).__name__)
            raise
        return self.kernel.seal(report)

    return wrapped
