"""AutonomyGarbageCollector: mutation responsibilities on the owning instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import digest
from .contracts import MutationGrant, ReclamationPlan

if TYPE_CHECKING:
    from hmt_edge_robot.assurance.agc import AutonomyGarbageCollector

def _execute(self: AutonomyGarbageCollector, plan: ReclamationPlan, grant: MutationGrant):
    db, ledger = self.kernel.ledger.db, self.kernel.ledger
    with ledger.lock, db:
        db.execute("BEGIN IMMEDIATE")
        self.catalog.verify()
        self._admit(plan, grant)
        decision = next(
            (d for d in plan.decisions if d.scope.subject_id == grant.artifact_id), None
        )
        if decision is None:
            raise PermissionError("ARTIFACT_NOT_IN_PLAN")
        row = self.catalog._row(grant.artifact_id)
        state = self._transition(row, grant.action, decision.verdict)
        timestamp = self.kernel.clock() if state == "QUARANTINE" else None
        db.execute(
            "UPDATE assurance_catalog SET state=?,quarantined_at=?,content=CASE WHEN ?='RECLAIMED' THEN NULL ELSE content END WHERE artifact_id=?",
            (state, timestamp, state, grant.artifact_id),
        )
        db.execute("UPDATE assurance_meta SET revision=revision+1")
        db.execute("UPDATE assurance_grants SET consumed=1 WHERE grant_id=?", (grant.grant_id,))
        import json

        ledger._append(
            "assurance",
            grant.artifact_id,
            "artifact_mutated",
            {
                "state": state,
                "record": json.loads(row[1]),
                "grant_id": grant.grant_id,
                "plan_hash": grant.plan_hash,
                "quarantined_at": timestamp,
            },
        )
        report = decision.model_copy(
            update={
                "verdict": "RESTORED" if state == "ACTIVE" else state,
                "reason_codes": ("GOVERNED_" + grant.action.upper(),),
                "dry_run": False,
            }
        )
        # Seal within the same transaction without nested context-manager commits.
        payload = report.model_dump(mode="json")
        report_hash = digest(payload)
        event_hash = ledger._append(
            "assurance",
            report_hash,
            "assurance_notice",
            {
                "report": payload,
                "report_hash": report_hash,
                "severity": "NOTICE",
                "requires_ack": False,
            },
        )
        from .contracts import SealedReport

        return SealedReport(report=report, report_hash=report_hash, event_hash=event_hash)

def _transition(self: AutonomyGarbageCollector, row, action, verdict):
    if action == "restore" and row[3] == "QUARANTINE":
        return "ACTIVE"
    if action == "quarantine" and row[3] == "ACTIVE" and verdict == "SAFE_TO_RECLAIM":
        return "QUARANTINE"
    if (
        action == "delete"
        and row[3] == "QUARANTINE"
        and verdict == "QUARANTINE"
        and row[4] is not None
        and self.kernel.clock() - row[4] >= self.dwell_sec
    ):
        return "RECLAIMED"
    raise PermissionError("RECLAMATION_TRANSITION_DENIED")
