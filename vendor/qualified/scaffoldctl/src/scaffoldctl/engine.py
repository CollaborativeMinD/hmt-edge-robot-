from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseTwoError, TransactionError
from scaffoldctl.integrity import (
    canonical_json_bytes,
    parse_strict_json,
    sha256_bytes,
    stamp_payload,
    verify_stamped_payload,
)
from scaffoldctl.lifecycle import LifecycleController
from scaffoldctl.models import (
    CriterionEvidence,
    TransitionReceipt,
    TransitionRequest,
    physical_line_count,
)
from scaffoldctl.ontology import verify_ontology_authority
from scaffoldctl.phase2_models import (
    ArtifactEvidence,
    ArtifactOperationDisposition,
    BoundarySpec,
    EntryKind,
    OperationName,
    OperationReceipt,
    PlanAction,
    PlanActionKind,
    RollbackStatus,
    ScaffoldPlan,
    ValidationFinding,
    canonical_target_path,
    expected_governed_paths,
    joined_relative_path,
)
from scaffoldctl.policy import (
    load_policy_pack,
    make_boundary_policy,
    parse_boundary_policy,
    render_boundary,
    verify_phase_two_resource_authority,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    ONTOLOGY_SHA256,
    PHASE_TWO_POLICY_PACK_SHA256,
    PHASE_TWO_TEMPLATE_PACK_SHA256,
    LifecycleState,
    LifecycleTrigger,
    ValidationStatus,
)
from scaffoldctl.snapshot import OverlaySnapshot, WorktreeSnapshot, snapshot_digest
from scaffoldctl.transaction import AtomicBatchWriter
from scaffoldctl.validation import validate_boundary, validate_document


def normalize_target_path(target_path: str) -> str:
    try:
        return canonical_target_path(target_path)
    except (TypeError, ValueError) as exc:
        reason = (
            ReasonCode.PATH_ABSOLUTE
            if str(target_path).startswith("/")
            else ReasonCode.PATH_TRAVERSAL
        )
        raise PhaseTwoError(reason, "target path is not canonical") from exc


def _transition(
    initial: LifecycleState,
    trigger: LifecycleTrigger,
    criterion_iri: str,
    evidence_id: str,
) -> TransitionReceipt:
    controller = LifecycleController(initial)
    request = TransitionRequest(
        trigger=trigger,
        criteria=(
            CriterionEvidence(
                criterionIri=criterion_iri,
                evidenceId=evidence_id,
                admitted=True,
            ),
        ),
    )
    return controller.advance(request)


def _stamp_plan(payload: dict[str, Any]) -> ScaffoldPlan:
    stamped = stamp_payload(payload, kind="scaffold-plan", id_field="planId", hash_field="planHash")
    return ScaffoldPlan.model_validate(stamped)


def verify_plan(plan: ScaffoldPlan) -> None:
    payload = plan.model_dump(mode="json")
    if not verify_stamped_payload(
        payload,
        kind="scaffold-plan",
        id_field="planId",
        hash_field="planHash",
    ):
        raise PhaseTwoError(ReasonCode.PLAN_INVALID, "plan hash or identity is invalid")
    if (
        plan.ontologySha256 != ONTOLOGY_SHA256
        or plan.policyPackSha256 != PHASE_TWO_POLICY_PACK_SHA256
        or plan.templatePackSha256 != PHASE_TWO_TEMPLATE_PACK_SHA256
    ):
        raise PhaseTwoError(ReasonCode.PLAN_INVALID, "plan authority hashes are invalid")
    pack = load_policy_pack()
    expected = expected_governed_paths(plan.boundary.targetPath, pack.policyFileName)
    if tuple(action.relativePath for action in plan.actions) != expected:
        raise PhaseTwoError(ReasonCode.PLAN_INVALID, "plan action set is not authoritative")


def load_plan(data: bytes) -> ScaffoldPlan:
    try:
        payload = parse_strict_json(data)
        plan = ScaffoldPlan.model_validate_json(canonical_json_bytes(payload))
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise PhaseTwoError(ReasonCode.PLAN_INVALID, "plan schema validation failed") from exc
    verify_plan(plan)
    return plan


def _stamp_receipt(payload: dict[str, Any]) -> OperationReceipt:
    stamped = stamp_payload(
        payload,
        kind="operation-receipt",
        id_field="receiptId",
        hash_field="receiptHash",
    )
    return OperationReceipt.model_validate(stamped)


def verify_receipt(receipt: OperationReceipt) -> None:
    if (
        receipt.ontologySha256 != ONTOLOGY_SHA256
        or receipt.policyPackSha256 != PHASE_TWO_POLICY_PACK_SHA256
        or receipt.templatePackSha256 != PHASE_TWO_TEMPLATE_PACK_SHA256
    ):
        raise PhaseTwoError(ReasonCode.RECEIPT_HASH_INVALID, "receipt authority is invalid")
    if not verify_stamped_payload(
        receipt.model_dump(mode="json"),
        kind="operation-receipt",
        id_field="receiptId",
        hash_field="receiptHash",
    ):
        raise PhaseTwoError(ReasonCode.RECEIPT_HASH_INVALID, "receipt hash or identity is invalid")


def load_receipt(data: bytes) -> OperationReceipt:
    try:
        payload = parse_strict_json(data)
        receipt = OperationReceipt.model_validate_json(canonical_json_bytes(payload))
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise PhaseTwoError(
            ReasonCode.RECEIPT_HASH_INVALID, "receipt schema validation failed"
        ) from exc
    verify_receipt(receipt)
    return receipt


def _unique_reason_codes(values: Iterable[ReasonCode]) -> tuple[ReasonCode, ...]:
    result: list[ReasonCode] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def make_receipt(
    *,
    operation: OperationName,
    status: ValidationStatus,
    exit_code: int,
    target_path: str,
    reasons: tuple[ReasonCode, ...],
    snapshot_before: str | None = None,
    snapshot_after: str | None = None,
    transition: TransitionReceipt | None = None,
    artifacts: tuple[ArtifactEvidence, ...] = (),
    findings: tuple[ValidationFinding, ...] = (),
    created_paths: tuple[str, ...] = (),
    preserved_paths: tuple[str, ...] = (),
    rollback_status: RollbackStatus = RollbackStatus.NONE,
    replayed_receipt_hash: str | None = None,
    error_class: str | None = None,
) -> OperationReceipt:
    payload = {
        "artifacts": artifacts,
        "createdPaths": created_paths,
        "errorClass": error_class,
        "exitCode": exit_code,
        "findings": findings,
        "lifecycleTransition": transition,
        "ontologySha256": ONTOLOGY_SHA256,
        "operation": operation,
        "policyPackSha256": PHASE_TWO_POLICY_PACK_SHA256,
        "preservedPaths": preserved_paths,
        "reasonCodes": _unique_reason_codes(reasons),
        "replayedReceiptHash": replayed_receipt_hash,
        "rollbackStatus": rollback_status,
        "schemaId": "urn:scaffoldctl:schema:operation-receipt:0.2.0",
        "schemaVersion": "0.2.0",
        "snapshotAfterSha256": snapshot_after,
        "snapshotBeforeSha256": snapshot_before,
        "targetPath": target_path,
        "templatePackSha256": PHASE_TWO_TEMPLATE_PACK_SHA256,
        "validationStatus": status,
    }
    return _stamp_receipt(payload)


def failure_receipt(
    operation: OperationName,
    target_path: str,
    error: BaseException,
) -> OperationReceipt:
    if isinstance(error, PhaseTwoError):
        reason = error.reason_code
        exit_code = error.exit_code
    else:
        reason = ReasonCode.INTERNAL_ERROR
        exit_code = 3
    rollback = RollbackStatus.NONE
    created: tuple[str, ...] = ()
    if isinstance(error, TransactionError):
        rollback = RollbackStatus.COMPLETE if error.rollback_complete else RollbackStatus.INCOMPLETE
        created = error.created_paths
    reasons = (
        (ReasonCode.TRANSACTION_COMMIT_FAILED, reason)
        if isinstance(error, TransactionError)
        else (reason,)
    )
    return make_receipt(
        operation=operation,
        status=ValidationStatus.FAIL,
        exit_code=exit_code,
        target_path=target_path,
        reasons=reasons,
        created_paths=created,
        rollback_status=rollback,
        error_class=type(error).__name__,
    )


class ScaffoldEngine:
    def __init__(self, root: str | Path) -> None:
        self.snapshot = WorktreeSnapshot(root)
        self.root = self.snapshot.root

    @staticmethod
    def _verify_authority() -> None:
        verify_ontology_authority()
        verify_phase_two_resource_authority()

    def _preserved_action(
        self,
        boundary: BoundarySpec,
        name: str,
        data: bytes,
    ) -> PlanAction:
        pack = load_policy_pack()
        path = joined_relative_path(boundary.targetPath, name)
        if name == pack.policyFileName:
            policy = parse_boundary_policy(data)
            if policy != make_boundary_policy(boundary):
                raise PhaseTwoError(ReasonCode.POLICY_AUTHORITY_DRIFT, "existing policy differs")
            line_count = None
        else:
            rule = next(
                item for item in pack.requiredDocuments if item.canonicalRelativePath == name
            )
            finding, artifact = validate_document(
                self.snapshot,
                boundary.targetPath,
                rule,
                pack.unresolvedPlaceholderTokens,
                pack.maximumDocumentUtf8Bytes,
            )
            if not finding.admitted or artifact is None:
                raise PhaseTwoError(
                    ReasonCode.EXISTING_CONTENT_INVALID, "existing document invalid"
                )
            line_count = artifact.lineCount
        return PlanAction(
            relativePath=path,
            action=PlanActionKind.PRESERVE,
            expectedSha256=sha256_bytes(data),
            sizeBytes=len(data),
            lineCount=line_count,
        )

    def _plan_actions(
        self,
        boundary: BoundarySpec,
        rendered: dict[str, bytes],
    ) -> tuple[PlanAction, ...]:
        pack = load_policy_pack()
        target_kind = self.snapshot.kind(boundary.targetPath)
        if target_kind not in {EntryKind.MISSING, EntryKind.DIRECTORY}:
            reason = (
                ReasonCode.PATH_SYMLINK_REJECTED
                if target_kind is EntryKind.SYMLINK
                else ReasonCode.TARGET_TYPE_INVALID
            )
            raise PhaseTwoError(reason, "target is not a directory or missing path")
        names = self.snapshot.list_dir(boundary.targetPath)
        if any(name.startswith(".scaffoldctl-") and name.endswith(".tmp") for name in names):
            raise PhaseTwoError(
                ReasonCode.TEMPORARY_ARTIFACT_PRESENT,
                "unfinished scaffold transaction requires review",
            )
        actions: list[PlanAction] = []
        for name, data in rendered.items():
            path = joined_relative_path(boundary.targetPath, name)
            kind = self.snapshot.kind(path)
            if kind is EntryKind.MISSING:
                line_count = (
                    physical_line_count(data.decode("utf-8"))
                    if name != pack.policyFileName
                    else None
                )
                actions.append(
                    PlanAction(
                        relativePath=path,
                        action=PlanActionKind.CREATE,
                        expectedSha256=sha256_bytes(data),
                        sizeBytes=len(data),
                        lineCount=line_count,
                    )
                )
            elif kind is EntryKind.FILE:
                data = self.snapshot.read_bytes(path, maximum_bytes=pack.maximumDocumentUtf8Bytes)
                actions.append(self._preserved_action(boundary, name, data))
            else:
                reason = (
                    ReasonCode.PATH_SYMLINK_REJECTED
                    if kind is EntryKind.SYMLINK
                    else ReasonCode.EXISTING_CONTENT_INVALID
                )
                raise PhaseTwoError(reason, "existing governed path is not a regular file")
        return tuple(actions)

    def plan(self, boundary: BoundarySpec) -> ScaffoldPlan:
        self._verify_authority()
        rendered = render_boundary(boundary)
        actions = self._plan_actions(boundary, rendered)
        pack = load_policy_pack()
        paths = expected_governed_paths(boundary.targetPath, pack.policyFileName)
        before = snapshot_digest(self.snapshot, boundary.targetPath, paths)
        transition = _transition(
            LifecycleState.UNINITIALIZED,
            LifecycleTrigger.PLAN,
            "urn:scaffoldctl:criterion:phase-2-plan-admitted",
            f"sha256:{before}",
        )
        payload = {
            "actions": actions,
            "boundary": boundary,
            "exitCode": 0,
            "lifecycleTransition": transition,
            "ontologySha256": ONTOLOGY_SHA256,
            "operation": OperationName.PLAN,
            "policyPackSha256": PHASE_TWO_POLICY_PACK_SHA256,
            "reasonCodes": (ReasonCode.PLAN_READY,),
            "schemaId": "urn:scaffoldctl:schema:scaffold-plan:0.2.0",
            "schemaVersion": "0.2.0",
            "snapshotBeforeSha256": before,
            "templatePackSha256": PHASE_TWO_TEMPLATE_PACK_SHA256,
            "validationStatus": ValidationStatus.PASS,
        }
        return _stamp_plan(payload)

    @staticmethod
    def _operation_artifacts(plan: ScaffoldPlan) -> tuple[ArtifactEvidence, ...]:
        return tuple(
            ArtifactEvidence(
                relativePath=action.relativePath,
                disposition=(
                    ArtifactOperationDisposition.CREATED
                    if action.action is PlanActionKind.CREATE
                    else ArtifactOperationDisposition.PRESERVED
                ),
                sha256=action.expectedSha256,
                sizeBytes=action.sizeBytes,
                lineCount=action.lineCount,
            )
            for action in plan.actions
        )

    def _scaffold_failure(
        self,
        plan: ScaffoldPlan,
        reasons: tuple[ReasonCode, ...],
        rollback: RollbackStatus,
        error_class: str,
    ) -> OperationReceipt:
        transition = _transition(
            LifecycleState.PLANNED,
            LifecycleTrigger.HOLD,
            "urn:scaffoldctl:criterion:phase-2-scaffold-hold",
            f"sha256:{plan.planHash}",
        )
        return make_receipt(
            operation=OperationName.SCAFFOLD,
            status=ValidationStatus.FAIL,
            exit_code=3,
            target_path=plan.boundary.targetPath,
            reasons=reasons,
            snapshot_before=plan.snapshotBeforeSha256,
            transition=transition,
            rollback_status=rollback,
            error_class=error_class,
        )

    def scaffold(self, plan: ScaffoldPlan) -> OperationReceipt:
        self._verify_authority()
        verify_plan(plan)
        current = self.plan(plan.boundary)
        if current.planHash != plan.planHash:
            raise PhaseTwoError(ReasonCode.PLAN_STALE, "worktree changed after planning")
        rendered = render_boundary(plan.boundary)
        creates = {
            action.relativePath: rendered[PurePosixPath(action.relativePath).name]
            for action in plan.actions
            if action.action is PlanActionKind.CREATE
        }
        pack = load_policy_pack()
        paths = expected_governed_paths(plan.boundary.targetPath, pack.policyFileName)
        candidate = OverlaySnapshot(self.snapshot, creates)
        candidate_outcome = validate_boundary(
            candidate,
            plan.boundary.targetPath,
            expected_boundary=plan.boundary,
        )
        if not candidate_outcome.admitted:
            raise PhaseTwoError(
                ReasonCode.TEMPLATE_RENDER_INVALID, "candidate scaffold failed validation"
            )
        expected_after = snapshot_digest(candidate, plan.boundary.targetPath, paths)
        preserved = tuple(
            action.relativePath
            for action in plan.actions
            if action.action is PlanActionKind.PRESERVE
        )
        if not creates:
            return self._scaffold_success(plan, expected_after, (), preserved, no_changes=True)
        return self._commit_scaffold(plan, creates, expected_after, preserved, paths)

    def _commit_scaffold(
        self,
        plan: ScaffoldPlan,
        creates: dict[str, bytes],
        expected_after: str,
        preserved: tuple[str, ...],
        governed_paths: tuple[str, ...],
    ) -> OperationReceipt:
        try:
            record = AtomicBatchWriter(self.root).commit(creates)
        except TransactionError as exc:
            rollback = (
                RollbackStatus.COMPLETE if exc.rollback_complete else RollbackStatus.INCOMPLETE
            )
            return self._scaffold_failure(
                plan,
                (ReasonCode.TRANSACTION_COMMIT_FAILED, exc.reason_code),
                rollback,
                exc.error_class,
            )
        temporary_names = record.temporary_names
        observed = WorktreeSnapshot(self.root)
        outcome = validate_boundary(
            observed,
            plan.boundary.targetPath,
            expected_boundary=plan.boundary,
            admitted_temporary_names=temporary_names,
        )
        observed_after = snapshot_digest(
            observed,
            plan.boundary.targetPath,
            governed_paths,
            ignored_names=temporary_names,
        )
        if not outcome.admitted or observed_after != expected_after:
            complete = record.rollback()
            reason = ReasonCode.WORKTREE_INVALID if not outcome.admitted else ReasonCode.PLAN_STALE
            rollback = RollbackStatus.COMPLETE if complete else RollbackStatus.INCOMPLETE
            return self._scaffold_failure(plan, (reason,), rollback, "PostCommitValidationError")
        try:
            record.finalize()
        except OSError as exc:
            complete = record.rollback()
            rollback = RollbackStatus.COMPLETE if complete else RollbackStatus.INCOMPLETE
            return self._scaffold_failure(
                plan, (ReasonCode.TRANSACTION_COMMIT_FAILED,), rollback, type(exc).__name__
            )
        return self._scaffold_success(
            plan,
            expected_after,
            record.created_paths,
            preserved,
            no_changes=False,
        )

    def _scaffold_success(
        self,
        plan: ScaffoldPlan,
        snapshot_after: str,
        created: tuple[str, ...],
        preserved: tuple[str, ...],
        *,
        no_changes: bool,
    ) -> OperationReceipt:
        transition = _transition(
            LifecycleState.PLANNED,
            LifecycleTrigger.SCAFFOLD,
            "urn:scaffoldctl:criterion:phase-2-scaffold-admitted",
            f"sha256:{snapshot_after}",
        )
        primary = ReasonCode.SCAFFOLD_NO_CHANGES if no_changes else ReasonCode.SCAFFOLD_CREATED
        reasons = (primary, ReasonCode.EXISTING_CONTENT_PRESERVED) if preserved else (primary,)
        return make_receipt(
            operation=OperationName.SCAFFOLD,
            status=ValidationStatus.PASS,
            exit_code=0,
            target_path=plan.boundary.targetPath,
            reasons=reasons,
            snapshot_before=plan.snapshotBeforeSha256,
            snapshot_after=snapshot_after,
            transition=transition,
            artifacts=self._operation_artifacts(plan),
            created_paths=created,
            preserved_paths=preserved,
        )

    def _inspect(self, target_path: str, operation: OperationName) -> OperationReceipt:
        self._verify_authority()
        target = normalize_target_path(target_path)
        pack = load_policy_pack()
        paths = expected_governed_paths(target, pack.policyFileName)
        outcome = validate_boundary(self.snapshot, target)
        try:
            digest = snapshot_digest(self.snapshot, target, paths)
        except PhaseTwoError:
            digest = None
        if operation is OperationName.AUDIT_WORKTREE:
            transition = None
        else:
            trigger = LifecycleTrigger.VALIDATE if outcome.admitted else LifecycleTrigger.HOLD
            transition = _transition(
                LifecycleState.SCAFFOLDED_UNVALIDATED,
                trigger,
                "urn:scaffoldctl:criterion:phase-2-worktree-inspected",
                f"sha256:{digest or ONTOLOGY_SHA256}",
            )
        status = ValidationStatus.PASS if outcome.admitted else ValidationStatus.FAIL
        reasons = (
            (ReasonCode.AUDIT_COMPLETE, *outcome.reason_codes)
            if operation is OperationName.AUDIT_WORKTREE
            else outcome.reason_codes
        )
        return make_receipt(
            operation=operation,
            status=status,
            exit_code=0 if outcome.admitted else 1,
            target_path=target,
            reasons=reasons,
            snapshot_before=digest,
            snapshot_after=digest,
            transition=transition,
            artifacts=outcome.artifacts,
            findings=outcome.findings,
        )

    def validate_worktree(self, target_path: str) -> OperationReceipt:
        return self._inspect(target_path, OperationName.VALIDATE_WORKTREE)

    def audit_worktree(
        self,
        target_path: str,
        replayed_receipt: OperationReceipt | None = None,
    ) -> OperationReceipt:
        if replayed_receipt is not None:
            verify_receipt(replayed_receipt)
        current = self._inspect(target_path, OperationName.AUDIT_WORKTREE)
        if replayed_receipt is None or current.validationStatus is not ValidationStatus.PASS:
            return current
        if replayed_receipt.snapshotAfterSha256 != current.snapshotAfterSha256:
            return make_receipt(
                operation=OperationName.AUDIT_WORKTREE,
                status=ValidationStatus.FAIL,
                exit_code=1,
                target_path=current.targetPath,
                reasons=(ReasonCode.RECEIPT_SNAPSHOT_MISMATCH,),
                snapshot_before=current.snapshotBeforeSha256,
                snapshot_after=current.snapshotAfterSha256,
                artifacts=current.artifacts,
                findings=current.findings,
                replayed_receipt_hash=replayed_receipt.receiptHash,
            )
        return make_receipt(
            operation=OperationName.AUDIT_WORKTREE,
            status=ValidationStatus.PASS,
            exit_code=0,
            target_path=current.targetPath,
            reasons=(
                ReasonCode.AUDIT_COMPLETE,
                ReasonCode.RECEIPT_VERIFIED,
                ReasonCode.WORKTREE_VALID,
            ),
            snapshot_before=current.snapshotBeforeSha256,
            snapshot_after=current.snapshotAfterSha256,
            artifacts=current.artifacts,
            findings=current.findings,
            replayed_receipt_hash=replayed_receipt.receiptHash,
        )
