from pathlib import Path

import pytest
from pydantic import ValidationError

import scaffoldctl.engine as engine_module
from scaffoldctl.engine import (
    ScaffoldEngine,
    failure_receipt,
    load_plan,
    load_receipt,
    make_receipt,
    normalize_target_path,
    verify_plan,
    verify_receipt,
)
from scaffoldctl.exceptions import PhaseTwoError, TransactionError
from scaffoldctl.integrity import canonical_json_bytes
from scaffoldctl.phase2_models import (
    ArtifactEvidence,
    ArtifactOperationDisposition,
    BoundarySpec,
    OperationName,
    PlanActionKind,
    RollbackStatus,
)
from scaffoldctl.policy import load_policy_pack, render_boundary
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import LifecycleState, ValidationStatus
from scaffoldctl.transaction import AtomicBatchWriter, CommitRecord
from scaffoldctl.validation import ValidationOutcome


def _boundary(target: str = "systems/demo", *, identifier: str = "systems.demo") -> BoundarySpec:
    return BoundarySpec(
        boundaryId=identifier,
        targetPath=target,
        title="Demo Boundary",
        purpose="Exercise the Phase 2 bounded core engine.",
    )


def _write_rendered(
    root: Path, boundary: BoundarySpec, names: tuple[str, ...] | None = None
) -> None:
    rendered = render_boundary(boundary)
    selected = tuple(rendered) if names is None else names
    target = root if boundary.targetPath == "." else root / boundary.targetPath
    target.mkdir(parents=True, exist_ok=True)
    for name in selected:
        (target / name).write_bytes(rendered[name])


def test_plan_is_deterministic_proof_carrying_and_nonmutating(tmp_path: Path) -> None:
    engine = ScaffoldEngine(tmp_path)
    boundary = _boundary()
    before = tuple(tmp_path.rglob("*"))
    first = engine.plan(boundary)
    second = engine.plan(boundary)
    assert first == second
    assert first.planId == second.planId
    assert first.planHash == second.planHash
    assert all(action.action is PlanActionKind.CREATE for action in first.actions)
    assert first.lifecycleTransition.fromState is LifecycleState.UNINITIALIZED
    assert first.lifecycleTransition.toState is LifecycleState.PLANNED
    assert tuple(tmp_path.rglob("*")) == before
    verify_plan(first)


@pytest.mark.parametrize("target", [".", "systems/demo", ".github/policy"])
def test_scaffold_validate_and_audit_end_to_end(tmp_path: Path, target: str) -> None:
    boundary = _boundary(target, identifier="root.demo")
    engine = ScaffoldEngine(tmp_path)
    plan = engine.plan(boundary)
    scaffold = engine.scaffold(plan)
    assert scaffold.validationStatus is ValidationStatus.PASS
    assert scaffold.reasonCodes == (ReasonCode.SCAFFOLD_CREATED,)
    assert scaffold.lifecycleTransition is not None
    assert scaffold.lifecycleTransition.toState is LifecycleState.SCAFFOLDED_UNVALIDATED
    assert len(scaffold.createdPaths) == 4
    assert scaffold.rollbackStatus is RollbackStatus.NONE
    validation = ScaffoldEngine(tmp_path).validate_worktree(target)
    assert validation.validationStatus is ValidationStatus.PASS
    assert validation.lifecycleTransition is not None
    assert validation.lifecycleTransition.toState is LifecycleState.VALIDATED
    assert len(validation.artifacts) == 4
    audit = ScaffoldEngine(tmp_path).audit_worktree(target, scaffold)
    assert audit.validationStatus is ValidationStatus.PASS
    assert ReasonCode.RECEIPT_VERIFIED in audit.reasonCodes
    verify_receipt(audit)


def test_partial_existing_boundary_is_preserved_and_completed(tmp_path: Path) -> None:
    boundary = _boundary()
    _write_rendered(tmp_path, boundary, ("README.md",))
    readme = tmp_path / boundary.targetPath / "README.md"
    before = readme.read_bytes()
    plan = ScaffoldEngine(tmp_path).plan(boundary)
    assert plan.actions[0].action is PlanActionKind.PRESERVE
    assert all(action.action is PlanActionKind.CREATE for action in plan.actions[1:])
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.PASS
    assert receipt.preservedPaths == (f"{boundary.targetPath}/README.md",)
    assert ReasonCode.EXISTING_CONTENT_PRESERVED in receipt.reasonCodes
    assert readme.read_bytes() == before


def test_complete_existing_boundary_is_idempotent(tmp_path: Path) -> None:
    boundary = _boundary()
    _write_rendered(tmp_path, boundary)
    before = {path: path.read_bytes() for path in (tmp_path / boundary.targetPath).iterdir()}
    plan = ScaffoldEngine(tmp_path).plan(boundary)
    assert all(action.action is PlanActionKind.PRESERVE for action in plan.actions)
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.PASS
    assert receipt.reasonCodes == (
        ReasonCode.SCAFFOLD_NO_CHANGES,
        ReasonCode.EXISTING_CONTENT_PRESERVED,
    )
    assert not receipt.createdPaths
    after = {path: path.read_bytes() for path in (tmp_path / boundary.targetPath).iterdir()}
    assert before == after


def test_plan_stales_on_direct_entry_or_governed_content_change(tmp_path: Path) -> None:
    boundary = _boundary()
    plan = ScaffoldEngine(tmp_path).plan(boundary)
    target = tmp_path / boundary.targetPath
    target.mkdir(parents=True)
    (target / "unrelated.txt").write_text("new", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).scaffold(plan)
    assert captured.value.reason_code is ReasonCode.PLAN_STALE


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (b"\xff", ReasonCode.EXISTING_CONTENT_INVALID),
        (b"line\n" * 100, ReasonCode.EXISTING_CONTENT_INVALID),
        (b"# Title\n\n## Purpose\n${OPEN}\n", ReasonCode.EXISTING_CONTENT_INVALID),
        (b"x" * 65537, ReasonCode.DOCUMENT_SIZE_INVALID),
    ],
)
def test_plan_rejects_invalid_existing_document(
    tmp_path: Path,
    mutation: bytes,
    expected: ReasonCode,
) -> None:
    boundary = _boundary()
    target = tmp_path / boundary.targetPath
    target.mkdir(parents=True)
    (target / "README.md").write_bytes(mutation)
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is expected


def test_plan_rejects_existing_policy_for_different_boundary(tmp_path: Path) -> None:
    expected = _boundary()
    different = BoundarySpec(
        boundaryId="different",
        targetPath=expected.targetPath,
        title="Different",
        purpose="Different policy identity.",
    )
    _write_rendered(tmp_path, different, (load_policy_pack().policyFileName,))
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(expected)
    assert captured.value.reason_code is ReasonCode.POLICY_AUTHORITY_DRIFT


def test_plan_rejects_target_file_symlink_case_collision_and_transaction_remnant(
    tmp_path: Path,
) -> None:
    boundary = _boundary("target")
    (tmp_path / "target").write_text("file", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is ReasonCode.TARGET_TYPE_INVALID
    (tmp_path / "target").unlink()
    (tmp_path / "target").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is ReasonCode.PATH_SYMLINK_REJECTED
    (tmp_path / "target").unlink()
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "readme.md").write_text("collision", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is ReasonCode.PATH_CASE_COLLISION
    (tmp_path / "target" / "readme.md").unlink()
    (tmp_path / "target" / ".scaffoldctl-orphan.tmp").write_text("orphan", encoding="utf-8")
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is ReasonCode.TEMPORARY_ARTIFACT_PRESENT


def test_plan_rejects_directory_at_governed_file_path(tmp_path: Path) -> None:
    boundary = _boundary("target")
    (tmp_path / "target" / "README.md").mkdir(parents=True)
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).plan(boundary)
    assert captured.value.reason_code is ReasonCode.EXISTING_CONTENT_INVALID


def test_validate_missing_and_invalid_boundary_is_fail_closed(tmp_path: Path) -> None:
    missing = ScaffoldEngine(tmp_path).validate_worktree("missing")
    assert missing.validationStatus is ValidationStatus.FAIL
    assert missing.exitCode == 1
    assert ReasonCode.TARGET_MISSING in missing.reasonCodes
    assert missing.lifecycleTransition is not None
    assert missing.lifecycleTransition.toState is LifecycleState.HOLD
    target = tmp_path / "target"
    target.mkdir()
    invalid = ScaffoldEngine(tmp_path).validate_worktree("target")
    assert ReasonCode.POLICY_MISSING in invalid.reasonCodes
    assert ReasonCode.DOCUMENT_MISSING in invalid.reasonCodes


def test_validate_does_not_mutate_invalid_worktree(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "user.txt").write_text("user", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    ScaffoldEngine(tmp_path).validate_worktree("target")
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert before == after


def test_plan_and_receipt_json_round_trip_and_tamper_rejection(tmp_path: Path) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    assert load_plan(canonical_json_bytes(plan)) == plan
    tampered = plan.model_dump(mode="json")
    tampered["planHash"] = "0" * 64
    with pytest.raises(PhaseTwoError) as captured:
        load_plan(canonical_json_bytes(tampered))
    assert captured.value.reason_code is ReasonCode.PLAN_INVALID
    with pytest.raises(PhaseTwoError):
        load_plan(b'{"schemaId":"x","schemaId":"y"}')
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert load_receipt(canonical_json_bytes(receipt)) == receipt
    receipt_payload = receipt.model_dump(mode="json")
    receipt_payload["exitCode"] = 9
    with pytest.raises(PhaseTwoError) as captured:
        load_receipt(canonical_json_bytes(receipt_payload))
    assert captured.value.reason_code is ReasonCode.RECEIPT_HASH_INVALID


def test_verify_plan_rejects_validly_hashed_wrong_action_order(tmp_path: Path) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    payload = plan.model_dump(mode="python", exclude={"planId", "planHash"})
    payload["actions"] = tuple(reversed(plan.actions))
    with pytest.raises(ValidationError):
        engine_module._stamp_plan(payload)


def test_audit_detects_snapshot_mismatch_and_invalid_receipt(tmp_path: Path) -> None:
    boundary = _boundary()
    plan = ScaffoldEngine(tmp_path).plan(boundary)
    scaffold = ScaffoldEngine(tmp_path).scaffold(plan)
    target = tmp_path / boundary.targetPath
    (target / "unrelated.txt").write_text("drift", encoding="utf-8")
    audit = ScaffoldEngine(tmp_path).audit_worktree(boundary.targetPath, scaffold)
    assert audit.validationStatus is ValidationStatus.FAIL
    assert audit.reasonCodes == (ReasonCode.RECEIPT_SNAPSHOT_MISMATCH,)
    tampered = scaffold.model_copy(update={"receiptHash": "0" * 64})
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).audit_worktree(boundary.targetPath, tampered)
    assert captured.value.reason_code is ReasonCode.RECEIPT_HASH_INVALID
    wrong_authority = scaffold.model_copy(update={"policyPackSha256": "0" * 64})
    with pytest.raises(PhaseTwoError) as captured:
        verify_receipt(wrong_authority)
    assert captured.value.reason_code is ReasonCode.RECEIPT_HASH_INVALID


def test_engine_rolls_back_mid_publish_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    original = AtomicBatchWriter._publish
    calls = 0

    def injected(self: AtomicBatchWriter, link: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        original(self, link)  # type: ignore[arg-type]

    monkeypatch.setattr(AtomicBatchWriter, "_publish", injected)
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.rollbackStatus is RollbackStatus.COMPLETE
    assert ReasonCode.TRANSACTION_COMMIT_FAILED in receipt.reasonCodes
    assert not tuple(tmp_path.rglob("README.md"))
    assert not tuple(tmp_path.rglob(".scaffoldctl-*.tmp"))


def test_engine_rolls_back_post_publish_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    original = engine_module.validate_boundary
    calls = 0

    def injected(*args: object, **kwargs: object) -> ValidationOutcome:
        nonlocal calls
        calls += 1
        if calls == 2:
            return ValidationOutcome(False, (ReasonCode.WORKTREE_INVALID,), (), (), None)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(engine_module, "validate_boundary", injected)
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.rollbackStatus is RollbackStatus.COMPLETE
    assert not tuple(tmp_path.rglob("scaffold.policy.json"))


def test_engine_rejects_invalid_candidate_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    monkeypatch.setattr(
        engine_module,
        "validate_boundary",
        lambda *args, **kwargs: ValidationOutcome(
            False,
            (ReasonCode.WORKTREE_INVALID,),
            (),
            (),
            None,
        ),
    )
    with pytest.raises(PhaseTwoError) as captured:
        ScaffoldEngine(tmp_path).scaffold(plan)
    assert captured.value.reason_code is ReasonCode.TEMPLATE_RENDER_INVALID
    assert not tuple(tmp_path.rglob("README.md"))


def test_engine_rolls_back_snapshot_parity_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())
    original = engine_module.snapshot_digest
    calls = 0

    def injected(*args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        value = original(*args, **kwargs)  # type: ignore[arg-type]
        return "0" * 64 if calls == 3 else value

    monkeypatch.setattr(engine_module, "snapshot_digest", injected)
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.reasonCodes == (ReasonCode.PLAN_STALE,)
    assert receipt.rollbackStatus is RollbackStatus.COMPLETE


def test_engine_handles_finalize_failure_with_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = ScaffoldEngine(tmp_path).plan(_boundary())

    def fail_finalize(self: CommitRecord) -> None:
        raise OSError("injected")

    monkeypatch.setattr(CommitRecord, "finalize", fail_finalize)
    receipt = ScaffoldEngine(tmp_path).scaffold(plan)
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.rollbackStatus is RollbackStatus.COMPLETE
    assert not tuple(tmp_path.rglob("README.md"))


def test_failure_receipts_cover_typed_transaction_and_internal_errors() -> None:
    typed = failure_receipt(
        OperationName.PLAN,
        ".",
        PhaseTwoError(ReasonCode.PLAN_INVALID, "bad"),
    )
    assert typed.reasonCodes == (ReasonCode.PLAN_INVALID,)
    transaction = failure_receipt(
        OperationName.SCAFFOLD,
        ".",
        TransactionError(
            "bad",
            rollback_complete=False,
            created_paths=("README.md",),
            error_class="OSError",
        ),
    )
    assert transaction.rollbackStatus is RollbackStatus.INCOMPLETE
    assert transaction.createdPaths == ("README.md",)
    internal = failure_receipt(OperationName.AUDIT_WORKTREE, ".", RuntimeError("bad"))
    assert internal.reasonCodes == (ReasonCode.INTERNAL_ERROR,)
    assert internal.exitCode == 3


def test_receipt_factory_deduplicates_reason_codes() -> None:
    receipt = make_receipt(
        operation=OperationName.AUDIT_WORKTREE,
        status=ValidationStatus.PASS,
        exit_code=0,
        target_path=".",
        reasons=(ReasonCode.AUDIT_COMPLETE, ReasonCode.AUDIT_COMPLETE),
    )
    assert receipt.reasonCodes == (ReasonCode.AUDIT_COMPLETE,)
    verify_receipt(receipt)


def test_operation_receipt_contract_rejects_duplicate_evidence_and_reasons() -> None:
    artifact = ArtifactEvidence(
        relativePath="README.md",
        disposition=ArtifactOperationDisposition.OBSERVED,
        sha256="0" * 64,
        sizeBytes=1,
        lineCount=1,
    )
    receipt = make_receipt(
        operation=OperationName.AUDIT_WORKTREE,
        status=ValidationStatus.PASS,
        exit_code=0,
        target_path=".",
        reasons=(ReasonCode.AUDIT_COMPLETE,),
        artifacts=(artifact,),
    )
    payload = receipt.model_dump(mode="python")
    payload["artifacts"] = (artifact, artifact)
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)
    payload = receipt.model_dump(mode="python")
    payload["reasonCodes"] = (ReasonCode.AUDIT_COMPLETE, ReasonCode.AUDIT_COMPLETE)
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)
    payload = receipt.model_dump(mode="python")
    payload["exitCode"] = 1
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)
    payload = receipt.model_dump(mode="python")
    payload["policyPackSha256"] = "0" * 64
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)
    payload = receipt.model_dump(mode="python")
    payload["createdPaths"] = ("README.md",)
    payload["preservedPaths"] = ("README.md",)
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)


def test_validate_target_file_exercises_unavailable_snapshot_digest(tmp_path: Path) -> None:
    (tmp_path / "target").write_text("file", encoding="utf-8")
    receipt = ScaffoldEngine(tmp_path).validate_worktree("target")
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.snapshotAfterSha256 is None


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (".", "."),
        ("a/b", "a/b"),
    ],
)
def test_normalize_target_path_accepts_canonical_values(target: str, expected: str) -> None:
    assert normalize_target_path(target) == expected


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("/absolute", ReasonCode.PATH_ABSOLUTE),
        ("../escape", ReasonCode.PATH_TRAVERSAL),
    ],
)
def test_normalize_target_path_reason_codes_invalid_values(
    target: str,
    reason: ReasonCode,
) -> None:
    with pytest.raises(PhaseTwoError) as captured:
        normalize_target_path(target)
    assert captured.value.reason_code is reason
