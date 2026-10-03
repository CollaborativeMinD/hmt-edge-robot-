from __future__ import annotations

import unicodedata
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from scaffoldctl.models import StrictFrozenModel, TransitionReceipt
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    HMT_REQUIRED_PATHS,
    ONTOLOGY_SHA256,
    PHASE_TWO_POLICY_FILE_NAME,
    PHASE_TWO_POLICY_PACK_SHA256,
    PHASE_TWO_TEMPLATE_PACK_SHA256,
    LifecycleState,
    LifecycleTrigger,
    ValidationStatus,
)

Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Uuid36 = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    ),
]


class EntryKind(StrEnum):
    MISSING = "missing"
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class PlanActionKind(StrEnum):
    CREATE = "create"
    PRESERVE = "preserve"


class OperationName(StrEnum):
    PLAN = "plan"
    SCAFFOLD = "scaffold"
    VALIDATE_WORKTREE = "validate_worktree"
    AUDIT_WORKTREE = "audit_worktree"


class ArtifactOperationDisposition(StrEnum):
    CREATED = "created"
    PRESERVED = "preserved"
    OBSERVED = "observed"


class RollbackStatus(StrEnum):
    NONE = "none"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


def _canonical_relative_path(value: str, *, root_allowed: bool) -> str:
    if value == "." and root_allowed:
        return value
    if not value or value.startswith("/"):
        raise ValueError("path must be non-empty and repository-relative")
    if "\\" in value or unicodedata.normalize("NFC", value) != value:
        raise ValueError("path must use canonical NFC POSIX spelling")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path contains traversal or non-canonical segments")
    for part in path.parts:
        if part[0] not in "._" and not (part[0].isascii() and part[0].isalnum()):
            raise ValueError("path segments must use portable alphanumeric spelling")
        if any(not (char.isascii() and (char.isalnum() or char in "._-")) for char in part):
            raise ValueError("path segments must use portable alphanumeric spelling")
    return value


def canonical_target_path(value: str) -> str:
    return _canonical_relative_path(value, root_allowed=True)


def canonical_artifact_path(value: str) -> str:
    return _canonical_relative_path(value, root_allowed=False)


def _single_line(value: str) -> str:
    if value != value.strip() or not value:
        raise ValueError("value must be non-empty without surrounding whitespace")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("value must use NFC Unicode normalization")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("control characters are not admitted")
    if any(token in value for token in ("${", "{{", "}}", "<<", ">>", "__SCAFFOLDCTL_")):
        raise ValueError("unresolved template tokens are not admitted")
    return value


class BoundarySpec(StrictFrozenModel):
    boundaryId: Annotated[
        str,
        StringConstraints(
            strict=True,
            min_length=1,
            max_length=64,
            pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        ),
    ]
    targetPath: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]
    title: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=120)]
    purpose: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]

    @field_validator("targetPath")
    @classmethod
    def target_is_canonical(cls, value: str) -> str:
        return canonical_target_path(value)

    @field_validator("title", "purpose")
    @classmethod
    def prose_is_bounded(cls, value: str) -> str:
        return _single_line(value)


class PolicyDocumentRule(StrictFrozenModel):
    canonicalRelativePath: Annotated[str, StringConstraints(strict=True, min_length=1)]
    maximumLineCountExclusive: Literal[100]
    requireSectionContent: Literal[True] = True
    requiredHeadings: Annotated[tuple[str, ...], Field(min_length=1, max_length=16)]

    @field_validator("canonicalRelativePath")
    @classmethod
    def document_path_is_canonical(cls, value: str) -> str:
        return canonical_artifact_path(value)

    @model_validator(mode="after")
    def headings_are_unique(self) -> PolicyDocumentRule:
        if len(set(self.requiredHeadings)) != len(self.requiredHeadings):
            raise ValueError("required headings must be unique")
        if any(not heading.startswith("## ") for heading in self.requiredHeadings):
            raise ValueError("required headings must be level-two Markdown headings")
        return self


class PolicyPack(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:hmt-root-policy:0.2.0"]
    schemaVersion: Literal["0.2.0"]
    policyId: Literal["scaffoldctl.hmt-root"]
    policyVersion: Literal["1.0.0"]
    ontologySha256: Sha256
    policyFileName: Literal["scaffold.policy.json"]
    maximumDocumentUtf8Bytes: Literal[65536]
    preserveExistingContent: Literal[True]
    rejectCaseCollisions: Literal[True]
    rejectSymlinks: Literal[True]
    requiredDocuments: Annotated[tuple[PolicyDocumentRule, ...], Field(min_length=3, max_length=3)]
    unresolvedPlaceholderTokens: Annotated[tuple[str, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def document_set_matches_ontology(self) -> PolicyPack:
        paths = tuple(rule.canonicalRelativePath for rule in self.requiredDocuments)
        if paths != HMT_REQUIRED_PATHS:
            raise ValueError("policy document order and paths must match ontology authority")
        if len(set(self.unresolvedPlaceholderTokens)) != len(self.unresolvedPlaceholderTokens):
            raise ValueError("placeholder tokens must be unique")
        return self


class BoundaryPolicy(PolicyPack):
    boundary: BoundarySpec


class PlanAction(StrictFrozenModel):
    relativePath: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1024)]
    action: PlanActionKind
    expectedSha256: Sha256
    sizeBytes: int = Field(strict=True, ge=0)
    lineCount: int | None = Field(default=None, strict=True, ge=0, lt=100)

    @field_validator("relativePath")
    @classmethod
    def path_is_canonical(cls, value: str) -> str:
        return canonical_artifact_path(value)


class ScaffoldPlan(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:scaffold-plan:0.2.0"]
    schemaVersion: Literal["0.2.0"]
    operation: Literal[OperationName.PLAN]
    validationStatus: Literal[ValidationStatus.PASS]
    exitCode: Literal[0]
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    boundary: BoundarySpec
    ontologySha256: Sha256
    policyPackSha256: Sha256
    templatePackSha256: Sha256
    snapshotBeforeSha256: Sha256
    actions: Annotated[tuple[PlanAction, ...], Field(min_length=4, max_length=4)]
    lifecycleTransition: TransitionReceipt
    planId: Uuid36
    planHash: Sha256

    @model_validator(mode="after")
    def plan_semantics_are_authoritative(self) -> ScaffoldPlan:
        paths = tuple(action.relativePath for action in self.actions)
        if len(set(paths)) != len(paths):
            raise ValueError("plan action paths must be unique")
        if paths != expected_governed_paths(self.boundary.targetPath, PHASE_TWO_POLICY_FILE_NAME):
            raise ValueError("plan action paths must match the complete governed set")
        if any(action.lineCount is None for action in self.actions[:-1]):
            raise ValueError("document plan actions require line-count evidence")
        if self.actions[-1].lineCount is not None:
            raise ValueError("policy plan action must not carry Markdown line-count evidence")
        if self.reasonCodes != (ReasonCode.PLAN_READY,):
            raise ValueError("plan reason code must state plan readiness")
        if (
            self.ontologySha256 != ONTOLOGY_SHA256
            or self.policyPackSha256 != PHASE_TWO_POLICY_PACK_SHA256
            or self.templatePackSha256 != PHASE_TWO_TEMPLATE_PACK_SHA256
        ):
            raise ValueError("plan authority hashes do not match the compiled authority")
        receipt = self.lifecycleTransition
        transition = receipt.transition
        if (
            not receipt.transitionAdmitted
            or receipt.trigger is not LifecycleTrigger.PLAN
            or receipt.fromState is not LifecycleState.UNINITIALIZED
            or receipt.toState is not LifecycleState.PLANNED
            or transition is None
            or transition.hasTransitionSource is not LifecycleState.UNINITIALIZED
            or transition.hasTransitionTarget is not LifecycleState.PLANNED
        ):
            raise ValueError("plan lifecycle evidence is not authoritative")
        return self


class ArtifactEvidence(StrictFrozenModel):
    relativePath: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1024)]
    disposition: ArtifactOperationDisposition
    sha256: Sha256
    sizeBytes: int = Field(strict=True, ge=0)
    lineCount: int | None = Field(default=None, strict=True, ge=0, lt=100)

    @field_validator("relativePath")
    @classmethod
    def path_is_canonical(cls, value: str) -> str:
        return canonical_artifact_path(value)


class ValidationFinding(StrictFrozenModel):
    relativePath: str
    admitted: bool
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    checkId: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128)]


class OperationReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:operation-receipt:0.2.0"]
    schemaVersion: Literal["0.2.0"]
    operation: OperationName
    validationStatus: ValidationStatus
    exitCode: int = Field(strict=True, ge=0, le=255)
    targetPath: str
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    ontologySha256: Sha256
    policyPackSha256: Sha256
    templatePackSha256: Sha256
    snapshotBeforeSha256: Sha256 | None
    snapshotAfterSha256: Sha256 | None
    lifecycleTransition: TransitionReceipt | None
    artifacts: tuple[ArtifactEvidence, ...]
    findings: tuple[ValidationFinding, ...]
    createdPaths: tuple[str, ...]
    preservedPaths: tuple[str, ...]
    rollbackStatus: RollbackStatus
    replayedReceiptHash: Sha256 | None
    errorClass: str | None
    receiptId: Uuid36
    receiptHash: Sha256

    @model_validator(mode="after")
    def receipt_semantics_are_consistent(self) -> OperationReceipt:
        paths = tuple(artifact.relativePath for artifact in self.artifacts)
        if len(set(paths)) != len(paths):
            raise ValueError("artifact evidence paths must be unique")
        if len(set(self.reasonCodes)) != len(self.reasonCodes):
            raise ValueError("receipt reason codes must be unique")
        if (self.validationStatus is ValidationStatus.PASS) != (self.exitCode == 0):
            raise ValueError("receipt status and exit code disagree")
        if (
            self.ontologySha256 != ONTOLOGY_SHA256
            or self.policyPackSha256 != PHASE_TWO_POLICY_PACK_SHA256
            or self.templatePackSha256 != PHASE_TWO_TEMPLATE_PACK_SHA256
        ):
            raise ValueError("receipt authority hashes do not match the compiled authority")
        governed_paths = (*self.createdPaths, *self.preservedPaths)
        if len(set(governed_paths)) != len(governed_paths):
            raise ValueError("created and preserved paths must be unique and disjoint")
        for path in governed_paths:
            canonical_artifact_path(path)
        return self


class SnapshotEntry(StrictFrozenModel):
    relativePath: str
    kind: EntryKind
    sizeBytes: int | None = Field(default=None, strict=True, ge=0)
    sha256: Sha256 | None = None


class PhaseTwoResourceAuthorityReceipt(StrictFrozenModel):
    validationStatus: Literal[ValidationStatus.PASS]
    reasonCodes: tuple[ReasonCode, ...]
    ontologySha256: Sha256
    policyPackSha256: Sha256
    templatePackSha256: Sha256
    receiptHash: Sha256


class PhaseTwoBuildAuthority(StrictFrozenModel):
    authorityId: Literal["scaffoldctl-phase-2-build-authority-v0.2.0"]
    promotedBaselineArchiveSha256: Sha256
    promotionReceiptId: Uuid36
    promotionReceiptSha256: Sha256
    promotionReportSha256: Sha256
    authorizationRef: Literal["user-directive:proceed-to-phase-2:2026-08-03"]
    authorizedScope: tuple[str, ...]
    nonclaims: tuple[str, ...]
    validationStatus: Literal[ValidationStatus.PASS]


def joined_relative_path(target: str, name: str) -> str:
    return name if target == "." else f"{target}/{name}"


def expected_governed_paths(target: str, policy_name: str) -> tuple[str, ...]:
    return tuple(joined_relative_path(target, name) for name in (*HMT_REQUIRED_PATHS, policy_name))


def state_for_validation(admitted: bool) -> LifecycleState:
    return LifecycleState.VALIDATED if admitted else LifecycleState.HOLD


def document_structure_status(
    text: str,
    required_headings: tuple[str, ...],
) -> tuple[bool, bool]:
    lines = tuple(line.strip() for line in text.splitlines())
    if sum(line.startswith("# ") for line in lines) != 1:
        return False, False
    if any(lines.count(heading) != 1 for heading in required_headings):
        return False, False
    for heading in required_headings:
        start = lines.index(heading) + 1
        end = next(
            (
                index
                for index in range(start, len(lines))
                if lines[index].startswith("# ") or lines[index].startswith("## ")
            ),
            len(lines),
        )
        if not any(line and not line.startswith("#") for line in lines[start:end]):
            return True, False
    return True, True
