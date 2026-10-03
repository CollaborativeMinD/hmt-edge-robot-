"""Dependency closure and fenced catalog reclamation with durable evidence before commit."""

from __future__ import annotations

from typing import Callable

from ..contracts import digest
from .catalog import ArtifactCatalog
from .contracts import AssuranceReport, Census, MutationGrant, ReclamationPlan, WitnessScope
from .kernel import AssuranceKernel


class AutonomyGarbageCollector:
    def __init__(
        self,
        kernel: AssuranceKernel,
        catalog: ArtifactCatalog,
        authorize: Callable[[MutationGrant], bool] = lambda _: False,
        dwell_sec: float = 60.0,
    ):
        if type(dwell_sec) is not float or not 0 <= dwell_sec <= 86400:
            raise ValueError("QUARANTINE_DWELL_INVALID")
        self.kernel, self.catalog, self.authorize, self.dwell_sec = (
            kernel,
            catalog,
            authorize,
            dwell_sec,
        )

    def plan(self, census: Census) -> ReclamationPlan:
        try:
            return self._plan(census)
        except Exception as exc:
            self.kernel.alert("AGC", "PLANNING_FAILED", type(exc).__name__)
            raise

    def _plan(self, census: Census) -> ReclamationPlan:
        decisions = self._decisions(census)
        for report in decisions:
            self.kernel.seal(report)
        plan = ReclamationPlan(
            census_hash=digest(census.model_dump(mode="json")),
            revision=census.revision,
            epochs=census.epochs,
            expires_at=census.expires_at,
            decisions=decisions,
        )
        self.kernel.ledger.append(
            "assurance",
            digest(plan.model_dump(mode="json")),
            "reclamation_plan",
            plan.model_dump(mode="json"),
        )
        return plan

    def _decisions(self, census: Census) -> tuple[AssuranceReport, ...]:
        records = {r.identity.artifact_id: r for r in census.records}
        unknown = (
            not census.complete
            or census.epochs != self.kernel.epochs()
            or not census.observed_at <= self.kernel.clock() < census.expires_at
            or any(
                r.epochs != census.epochs or set(r.dependencies) - records.keys()
                for r in records.values()
            )
        )
        protected = {}
        for key, r in records.items():
            if r.authority_refs:
                protected[key] = "LIVE"
            elif r.recovery_refs or r.cold_start_refs:
                protected[key] = "RECOVERY_REQUIRED"
            elif r.evidence_refs or r.side_effect_refs:
                protected[key] = "EVIDENCE_REQUIRED"
        frontier = sorted(protected)
        while frontier:
            key = frontier.pop()
            for dependency in records[key].dependencies:
                if dependency in records and dependency not in protected:
                    protected[dependency] = protected[key]
                    frontier.append(dependency)
        census_hash = digest(census.model_dump(mode="json"))
        return tuple(
            self._decision(
                r,
                census,
                "UNKNOWN_HOLD" if unknown else protected.get(key, "SAFE_TO_RECLAIM"),
                census_hash,
            )
            for key, r in sorted(records.items())
        )

    def _decision(self, record, census, verdict, census_hash):
        scope = WitnessScope(
            subject_id=record.identity.artifact_id,
            subject_hash=record.identity.identity_hash,
            contract_hash=census_hash,
            collector_id="managed-catalog",
            epochs=self.kernel.epochs(),
            observed_at=census.observed_at,
            expires_at=census.expires_at,
            coverage=("authority", "recovery", "evidence", "effects", "dependency_closure"),
        )
        if verdict == "SAFE_TO_RECLAIM":
            with self.kernel.ledger.lock:
                row = self.kernel.ledger.db.execute(
                    "SELECT state FROM assurance_catalog WHERE artifact_id=?",
                    (record.identity.artifact_id,),
                ).fetchone()
            if row and row[0] == "QUARANTINE":
                verdict = "QUARANTINE"
        return AssuranceReport(
            component="AGC",
            scope=scope,
            verdict=verdict,
            reason_codes=("AGC_" + verdict,),
            observation_hash=digest(record.model_dump(mode="json")),
            artifact_refs=record.dependencies,
        )

    def execute(self, plan: ReclamationPlan, grant: MutationGrant):
        try:
            return self._execute(plan, grant)
        except Exception as exc:
            self.kernel.alert("AGC", "MUTATION_DENIED_OR_FAILED", type(exc).__name__)
            raise

    def _execute(self, plan: ReclamationPlan, grant: MutationGrant):
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

    def _admit(self, plan, grant):
        now = self.kernel.clock()
        issued = self.kernel.ledger.db.execute(
            "SELECT grant_hash,consumed FROM assurance_grants WHERE grant_id=?", (grant.grant_id,)
        ).fetchone()
        issued_event = self.kernel.ledger.db.execute(
            "SELECT payload FROM events WHERE request_id=? AND packet_type='mutation_authority_issued'",
            (grant.grant_id,),
        ).fetchone()
        import json

        genuine = issued_event and json.loads(issued_event[0]) == grant.model_dump(mode="json")
        revision = self.kernel.ledger.db.execute("SELECT revision FROM assurance_meta").fetchone()[
            0
        ]
        if (
            not genuine
            or not issued
            or issued != (digest(grant.model_dump(mode="json")), 0)
            or not self.authorize(grant)
            or grant.plan_hash != digest(plan.model_dump(mode="json"))
            or grant.epochs != self.kernel.epochs()
            or plan.epochs != grant.epochs
            or plan.revision != revision
            or grant.revision != revision
            or now >= min(plan.expires_at, grant.expires_at)
        ):
            raise PermissionError("MUTATION_AUTHORITY_OR_FENCE_INVALID")
        # Never accept caller-forged decisions, even with a grant: reconstruct census and decisions.
        rows = self.kernel.ledger.db.execute(
            "SELECT record FROM assurance_catalog WHERE state!='RECLAIMED' ORDER BY artifact_id"
        ).fetchall()
        from .contracts import ArtifactRecord

        census = Census(
            epochs=plan.epochs,
            revision=revision,
            observed_at=plan.decisions[0].scope.observed_at if plan.decisions else now,
            expires_at=plan.expires_at,
            complete=True,
            records=tuple(ArtifactRecord.model_validate_json(r[0]) for r in rows),
        )
        if (
            digest(census.model_dump(mode="json")) != plan.census_hash
            or self._decisions(census) != plan.decisions
        ):
            raise PermissionError("PLAN_RECONSTRUCTION_MISMATCH")

    def _transition(self, row, action, verdict):
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
