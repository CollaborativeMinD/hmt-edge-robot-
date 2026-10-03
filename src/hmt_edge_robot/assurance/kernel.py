"""Canonical transformation kernel, durable notification outbox and observer decorator."""

from __future__ import annotations

import functools
import math
from typing import Callable

from ..contracts import Contract, digest
from ..ledger import Ledger
from .contracts import AssuranceReport, Epochs, SealedReport, WitnessScope
from .kernel_observer import acknowledge, alert, notices


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

    alert = alert

    notices = notices

    acknowledge = acknowledge


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
