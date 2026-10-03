from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.integrity import sha256_bytes
from scaffoldctl.models import RepositoryRootDirectory, document_from_text, physical_line_count
from scaffoldctl.phase2_models import (
    ArtifactEvidence,
    ArtifactOperationDisposition,
    BoundaryPolicy,
    BoundarySpec,
    EntryKind,
    PolicyDocumentRule,
    PolicyPack,
    ValidationFinding,
    document_structure_status,
    joined_relative_path,
)
from scaffoldctl.policy import load_policy_pack, parse_boundary_policy
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.snapshot import RepositorySnapshot


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    admitted: bool
    reason_codes: tuple[ReasonCode, ...]
    findings: tuple[ValidationFinding, ...]
    artifacts: tuple[ArtifactEvidence, ...]
    policy: BoundaryPolicy | None


def _finding(path: str, admitted: bool, reason: ReasonCode, check_id: str) -> ValidationFinding:
    return ValidationFinding(
        relativePath=path,
        admitted=admitted,
        reasonCodes=(reason,),
        checkId=check_id,
    )


def _artifact(path: str, data: bytes, *, line_count: int | None) -> ArtifactEvidence:
    return ArtifactEvidence(
        relativePath=path,
        disposition=ArtifactOperationDisposition.OBSERVED,
        sha256=sha256_bytes(data),
        sizeBytes=len(data),
        lineCount=line_count,
    )


def validate_document(
    snapshot: RepositorySnapshot,
    target_path: str,
    rule: PolicyDocumentRule,
    placeholder_tokens: tuple[str, ...],
    maximum_bytes: int,
) -> tuple[ValidationFinding, ArtifactEvidence | None]:
    path = joined_relative_path(target_path, rule.canonicalRelativePath)
    kind = snapshot.kind(path)
    if kind is EntryKind.MISSING:
        return _finding(path, False, ReasonCode.DOCUMENT_MISSING, "SCF.DOC.PRESENCE"), None
    if kind is EntryKind.SYMLINK:
        return _finding(path, False, ReasonCode.PATH_SYMLINK_REJECTED, "SCF.DOC.SYMLINK"), None
    if kind is not EntryKind.FILE:
        return _finding(path, False, ReasonCode.DOCUMENT_NOT_FILE, "SCF.DOC.TYPE"), None
    entry = snapshot.entry(path, include_hash=False)
    if entry.sizeBytes is None or entry.sizeBytes > maximum_bytes:
        return _finding(path, False, ReasonCode.DOCUMENT_SIZE_INVALID, "SCF.DOC.BYTES"), None
    try:
        data = snapshot.read_bytes(path, maximum_bytes=maximum_bytes)
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return _finding(path, False, ReasonCode.DOCUMENT_UTF8_INVALID, "SCF.DOC.UTF8"), None
    except PhaseTwoError as exc:
        return _finding(path, False, exc.reason_code, "SCF.DOC.READ"), None
    line_count = physical_line_count(text)
    if line_count >= rule.maximumLineCountExclusive:
        return _finding(path, False, ReasonCode.LINE_COUNT_INVALID, "SCF.DOC.LINE_BUDGET"), None
    try:
        document_from_text(rule.canonicalRelativePath, text)
    except (TypeError, ValueError, ValidationError):
        return _finding(path, False, ReasonCode.SCHEMA_INVALID, "SCF.DOC.SCHEMA"), None
    headings_admitted, sections_admitted = document_structure_status(text, rule.requiredHeadings)
    if not headings_admitted:
        return _finding(
            path,
            False,
            ReasonCode.DOCUMENT_HEADING_INVALID,
            "SCF.DOC.HEADINGS",
        ), None
    if any(token in text for token in placeholder_tokens):
        return _finding(path, False, ReasonCode.PLACEHOLDER_UNRESOLVED, "SCF.DOC.PLACEHOLDER"), None
    if rule.requireSectionContent and not sections_admitted:
        return _finding(
            path,
            False,
            ReasonCode.DOCUMENT_SECTION_EMPTY,
            "SCF.DOC.SECTION_CONTENT",
        ), None
    return (
        _finding(path, True, ReasonCode.DOCUMENT_VALID, "SCF.DOC.COMPLETE"),
        _artifact(path, data, line_count=line_count),
    )


def _validate_policy(
    snapshot: RepositorySnapshot,
    target_path: str,
    expected_boundary: BoundarySpec | None,
    pack: PolicyPack,
) -> tuple[ValidationFinding, ArtifactEvidence | None, BoundaryPolicy | None]:
    path = joined_relative_path(target_path, pack.policyFileName)
    kind = snapshot.kind(path)
    if kind is EntryKind.MISSING:
        return _finding(path, False, ReasonCode.POLICY_MISSING, "SCF.POLICY.PRESENCE"), None, None
    if kind is EntryKind.SYMLINK:
        return (
            _finding(path, False, ReasonCode.PATH_SYMLINK_REJECTED, "SCF.POLICY.SYMLINK"),
            None,
            None,
        )
    if kind is not EntryKind.FILE:
        return _finding(path, False, ReasonCode.POLICY_INVALID, "SCF.POLICY.TYPE"), None, None
    try:
        data = snapshot.read_bytes(path, maximum_bytes=pack.maximumDocumentUtf8Bytes)
        policy = parse_boundary_policy(data, authority=pack)
    except PhaseTwoError as exc:
        return _finding(path, False, exc.reason_code, "SCF.POLICY.SCHEMA"), None, None
    if policy.boundary.targetPath != target_path or (
        expected_boundary is not None and policy.boundary != expected_boundary
    ):
        return (
            _finding(path, False, ReasonCode.POLICY_AUTHORITY_DRIFT, "SCF.POLICY.BOUNDARY"),
            None,
            None,
        )
    return (
        _finding(path, True, ReasonCode.POLICY_VERIFIED, "SCF.POLICY.COMPLETE"),
        _artifact(path, data, line_count=None),
        policy,
    )


def _unique_reasons(findings: tuple[ValidationFinding, ...]) -> tuple[ReasonCode, ...]:
    reasons: list[ReasonCode] = []
    for finding in findings:
        for reason in finding.reasonCodes:
            if reason not in reasons:
                reasons.append(reason)
    return tuple(reasons)


def _invalid_target(
    target_path: str,
    kind: EntryKind,
    invalid_reason: ReasonCode,
) -> ValidationOutcome:
    reason = (
        ReasonCode.TARGET_MISSING
        if kind is EntryKind.MISSING
        else ReasonCode.PATH_SYMLINK_REJECTED
        if kind is EntryKind.SYMLINK
        else ReasonCode.TARGET_TYPE_INVALID
    )
    finding = _finding(target_path, False, reason, "SCF.TARGET.DIRECTORY")
    return ValidationOutcome(False, (reason, invalid_reason), (finding,), (), None)


def _recovery_findings(
    snapshot: RepositorySnapshot,
    target_path: str,
    admitted_temporary_names: tuple[str, ...],
) -> list[ValidationFinding]:
    admitted = set(admitted_temporary_names)
    unexpected = any(
        name.startswith(".scaffoldctl-") and name.endswith(".tmp") and name not in admitted
        for name in snapshot.list_dir(target_path)
    )
    if not unexpected:
        return []
    return [
        _finding(
            target_path,
            False,
            ReasonCode.TEMPORARY_ARTIFACT_PRESENT,
            "SCF.TRANSACTION.RECOVERY",
        )
    ]


def _validate_documents(
    snapshot: RepositorySnapshot,
    target_path: str,
    pack: PolicyPack,
) -> tuple[list[ValidationFinding], list[ArtifactEvidence]]:
    findings: list[ValidationFinding] = []
    artifacts: list[ArtifactEvidence] = []
    documents = []
    for rule in pack.requiredDocuments:
        finding, artifact = validate_document(
            snapshot,
            target_path,
            rule,
            pack.unresolvedPlaceholderTokens,
            pack.maximumDocumentUtf8Bytes,
        )
        findings.append(finding)
        if artifact is None:
            continue
        artifacts.append(artifact)
        data = snapshot.read_bytes(
            artifact.relativePath,
            maximum_bytes=pack.maximumDocumentUtf8Bytes,
        )
        documents.append(document_from_text(rule.canonicalRelativePath, data.decode("utf-8")))
    if len(documents) == len(pack.requiredDocuments):
        RepositoryRootDirectory(hasHMTTrifectaDocument=tuple(documents))
    return findings, artifacts


def validate_boundary(
    snapshot: RepositorySnapshot,
    target_path: str,
    *,
    expected_boundary: BoundarySpec | None = None,
    admitted_temporary_names: tuple[str, ...] = (),
    snapshot_valid_reason: ReasonCode = ReasonCode.WORKTREE_VALID,
    snapshot_invalid_reason: ReasonCode = ReasonCode.WORKTREE_INVALID,
) -> ValidationOutcome:
    pack = load_policy_pack()
    target_kind = snapshot.kind(target_path)
    if target_kind is not EntryKind.DIRECTORY:
        return _invalid_target(target_path, target_kind, snapshot_invalid_reason)
    findings = _recovery_findings(snapshot, target_path, admitted_temporary_names)
    policy_finding, policy_artifact, policy = _validate_policy(
        snapshot,
        target_path,
        expected_boundary,
        pack,
    )
    findings.append(policy_finding)
    artifacts: list[ArtifactEvidence] = []
    if policy_artifact is not None:
        artifacts.append(policy_artifact)
    document_findings, document_artifacts = _validate_documents(snapshot, target_path, pack)
    findings.extend(document_findings)
    artifacts.extend(document_artifacts)
    admitted = all(finding.admitted for finding in findings)
    if admitted:
        reasons = (
            ReasonCode.POLICY_VERIFIED,
            ReasonCode.TRIFECTA_VALID,
            ReasonCode.SCHEMA_VALID,
            snapshot_valid_reason,
        )
    else:
        reasons = (*_unique_reasons(tuple(findings)), snapshot_invalid_reason)
    return ValidationOutcome(admitted, reasons, tuple(findings), tuple(artifacts), policy)
