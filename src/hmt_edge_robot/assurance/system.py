"""Resident software composition with current operator admission and shared evidence."""

from __future__ import annotations

from ..contracts import digest
from .agc import AutonomyGarbageCollector
from .analytics import AssuranceAnalytics
from .catalog import ArtifactCatalog
from .contracts import Epochs, MutationAction, ReclamationPlan
from .kernel import AssuranceKernel
from .mcc import MissionColdStartCartographer
from .usea import UndeclaredSideEffectAttestor


class SubstrateAssurance:
    def __init__(self, cell, read_only: bool = False):
        self.cell = cell
        self.kernel = AssuranceKernel(
            cell.ledger, cell.clock, lambda: Epochs(policy=cell.policy.policy_epoch)
        )
        self.catalog = ArtifactCatalog(cell.ledger, cell.clock, self.kernel.epochs, read_only)
        self.mcc = MissionColdStartCartographer(self.kernel)
        self.usea = UndeclaredSideEffectAttestor(self.kernel)
        self.agc = AutonomyGarbageCollector(
            self.kernel,
            self.catalog,
            lambda grant: cell.access.authorize(
                grant.session_id, grant.operator_id, "reset", cell.clock()
            ),
        )
        self.analytics = AssuranceAnalytics(self.kernel)

    def issue_grant(
        self,
        plan: ReclamationPlan,
        action: MutationAction,
        artifact_id: str,
        session_id: str,
        operator_id: str,
    ):
        with self.cell.lock:
            if not self.cell.access.authorize(session_id, operator_id, "reset", self.cell.clock()):
                raise PermissionError("RECLAMATION_AUTHORITY_NOT_ADMITTED")
            if plan.epochs != self.kernel.epochs() or self.cell.clock() >= plan.expires_at:
                raise PermissionError("RECLAMATION_PLAN_STALE")
            return self.catalog.issue(
                digest(plan.model_dump(mode="json")),
                plan.revision,
                action,
                artifact_id,
                min(plan.expires_at, self.cell.clock() + 30.0),
                operator_id,
                session_id,
            )

    def mutate(self, plan, grant):
        with self.cell.lock:
            return self.agc.execute(plan, grant)

    def bind_witness(self, sealed, session_id: str, operator_id: str) -> int:
        """Bind MCC dependencies / USEA produced or touched artifacts conservatively to retention."""
        from .contracts import ArtifactRecord

        with self.cell.lock, self.cell.ledger.lock, self.cell.ledger.db:
            if not self.cell.access.authorize(session_id, operator_id, "reset", self.cell.clock()):
                raise PermissionError("REFERENCE_AUTHORITY_NOT_ADMITTED")
            if (
                sealed.report_hash != digest(sealed.report.model_dump(mode="json"))
                or not self.kernel.valid(sealed.report.scope)
                or sealed.report.component not in {"MCC", "USEA"}
            ):
                raise PermissionError("WITNESS_BINDING_INVALID")
            event = self.cell.ledger.db.execute(
                "SELECT payload FROM events WHERE determinism_hash=? AND request_id=? AND packet_type='assurance_notice'",
                (sealed.event_hash, sealed.report_hash),
            ).fetchone()
            import json

            if not event or json.loads(event[0]).get("report") != sealed.report.model_dump(
                mode="json"
            ):
                raise PermissionError("WITNESS_NOT_IN_EVIDENCE")
            self.cell.ledger.db.execute("BEGIN IMMEDIATE")
            self.catalog.verify()
            field = "cold_start_refs" if sealed.report.component == "MCC" else "side_effect_refs"
            for artifact in sealed.report.artifact_refs:
                row = self.catalog._row(artifact)
                if row[3] == "RECLAIMED":
                    raise PermissionError("REFERENCE_TO_RECLAIMED_ARTIFACT")
                record = ArtifactRecord.model_validate_json(row[1])
                payload = record.model_dump(mode="python")
                payload[field] = tuple(sorted(set(payload[field]) | {sealed.report_hash}))
                updated = ArtifactRecord.model_validate(payload)
                self.cell.ledger.db.execute(
                    "UPDATE assurance_catalog SET record=? WHERE artifact_id=?",
                    (updated.model_dump_json(), artifact),
                )
                self.catalog._changed("artifact_references_changed", updated)
            return len(sealed.report.artifact_refs)
