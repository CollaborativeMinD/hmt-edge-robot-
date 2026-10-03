from __future__ import annotations

import base64
import binascii
import unicodedata
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from scaffoldctl.integrity import hash_payload
from scaffoldctl.models import StrictFrozenModel
from scaffoldctl.phase2_models import ArtifactEvidence, ValidationFinding
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus

Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
ObjectId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
]
Uuid36 = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    ),
]
UtcTimestamp = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z$",
    ),
]
Base64Value = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=4, max_length=4096, pattern=r"^[A-Za-z0-9+/]+={0,2}$"
    ),
]


class GitSnapshotSource(StrEnum):
    INDEX = "git_index"
    TREE = "git_tree"


class GitObjectFormat(StrEnum):
    SHA1 = "sha1"
    SHA256 = "sha256"


class PerimeterOperation(StrEnum):
    VALIDATE_STAGED = "validate_staged"
    VALIDATE_TREE = "validate_tree"


class LeasePurpose(StrEnum):
    PRE_COMMIT = "pre_commit"
    CI_ADMISSION = "ci_admission"


class SignerProvenance(StrEnum):
    LOCAL_REPOSITORY_KEY = "local_repository_key"
    CI_EPHEMERAL_KEY = "ci_ephemeral_key"
    CI_SECRET_KEY = "ci_secret_key"
    RELEASE_KEY = "release_key"


def canonical_git_path(value: str) -> str:
    if not value or value.startswith("/") or "\\" in value:
        raise ValueError("Git path must be a repository-relative POSIX path")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("Git path must use NFC normalization")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Git path contains a control character")
    path = PurePosixPath(value)
    if str(path) != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Git path contains traversal or non-canonical segments")
    return value


def _collision_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _validate_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return value


def _validate_b64(value: str) -> str:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("value is not canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("value is not canonical base64")
    return value


class GitObjectEntry(StrictFrozenModel):
    relativePath: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]
    objectMode: Literal["100644", "100755", "120000", "160000"]
    objectType: Literal["blob", "commit"]
    objectId: ObjectId
    objectSize: int | None = Field(default=None, strict=True, ge=0)
    stage: Literal[0]

    @field_validator("relativePath")
    @classmethod
    def path_is_canonical(cls, value: str) -> str:
        return canonical_git_path(value)

    @model_validator(mode="after")
    def mode_and_type_are_consistent(self) -> GitObjectEntry:
        is_gitlink = self.objectMode == "160000"
        if is_gitlink != (self.objectType == "commit"):
            raise ValueError("only mode 160000 may reference a commit")
        if is_gitlink != (self.objectSize is None):
            raise ValueError("gitlink size must be absent and blob size must be present")
        return self


class GitObjectMatrix(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:git-object-matrix:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    sourceKind: GitSnapshotSource
    sourceRef: str
    objectFormat: GitObjectFormat
    entryCount: int = Field(strict=True, ge=0)
    entries: tuple[GitObjectEntry, ...]
    contentMatrixSha256: Sha256
    matrixSha256: Sha256

    @model_validator(mode="after")
    def matrix_is_canonical(self) -> GitObjectMatrix:
        if self.entryCount != len(self.entries):
            raise ValueError("entry count does not match matrix")
        paths = tuple(entry.relativePath for entry in self.entries)
        if paths != tuple(sorted(paths, key=lambda item: item.encode("utf-8"))):
            raise ValueError("matrix paths are not bytewise sorted")
        if len({_collision_key(path) for path in paths}) != len(paths):
            raise ValueError("matrix contains a case or NFKC collision")
        path_set = set(paths)
        for path in paths:
            parent = PurePosixPath(path).parent
            while str(parent) != ".":
                if parent.as_posix() in path_set:
                    raise ValueError("matrix contains a directory/file conflict")
                parent = parent.parent
        if self.sourceKind is GitSnapshotSource.INDEX:
            if self.sourceRef != "INDEX":
                raise ValueError("index matrix source reference must be INDEX")
        elif (
            self.sourceRef != self.sourceRef.lower()
            or len(self.sourceRef) not in {40, 64}
            or any(character not in "0123456789abcdef" for character in self.sourceRef)
        ):
            raise ValueError("tree matrix source reference must be a full object id")
        entries_payload = tuple(entry.model_dump(mode="json") for entry in self.entries)
        expected_content = hash_payload(entries_payload)
        expected_matrix = hash_payload(
            {
                "contentMatrixSha256": expected_content,
                "objectFormat": self.objectFormat,
                "sourceKind": self.sourceKind,
                "sourceRef": self.sourceRef,
            }
        )
        if self.contentMatrixSha256 != expected_content or self.matrixSha256 != expected_matrix:
            raise ValueError("matrix hash does not match canonical content")
        return self


class BoundaryValidationRecord(StrictFrozenModel):
    targetPath: str
    validationStatus: ValidationStatus
    admitted: bool
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    findings: tuple[ValidationFinding, ...]
    artifacts: tuple[ArtifactEvidence, ...]

    @model_validator(mode="after")
    def disposition_is_consistent(self) -> BoundaryValidationRecord:
        if self.admitted != (self.validationStatus is ValidationStatus.PASS):
            raise ValueError("boundary status and admission disagree")
        return self


class PerimeterValidationReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:perimeter-validation-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    operation: PerimeterOperation
    sourceKind: GitSnapshotSource
    sourceRef: str
    matrixSha256: Sha256 | None
    contentMatrixSha256: Sha256 | None
    baselineContentMatrixSha256: Sha256 | None
    boundarySetSha256: Sha256 | None
    boundaries: tuple[BoundaryValidationRecord, ...]
    validationStatus: ValidationStatus
    exitCode: Literal[0, 1]
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    recordedAtUtc: UtcTimestamp
    receiptId: Uuid36
    receiptHash: Sha256

    @field_validator("recordedAtUtc")
    @classmethod
    def timestamp_is_utc(cls, value: str) -> str:
        return _validate_timestamp(value)

    @model_validator(mode="after")
    def receipt_is_consistent(self) -> PerimeterValidationReceipt:
        if (self.validationStatus is ValidationStatus.PASS) != (self.exitCode == 0):
            raise ValueError("perimeter status and exit code disagree")
        if len(set(self.reasonCodes)) != len(self.reasonCodes):
            raise ValueError("perimeter reason codes must be unique")
        if self.validationStatus is ValidationStatus.PASS:
            if (
                None
                in (
                    self.matrixSha256,
                    self.contentMatrixSha256,
                    self.boundarySetSha256,
                )
                or not self.boundaries
            ):
                raise ValueError("passing receipt requires complete matrix and boundary evidence")
            if not all(boundary.admitted for boundary in self.boundaries):
                raise ValueError("passing perimeter contains a rejected boundary")
        return self


class AssetLease(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:signed-asset-lease:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    leaseId: Uuid36
    validationReceiptId: Uuid36
    validationReceiptHash: Sha256
    purpose: LeasePurpose
    sourceKind: GitSnapshotSource
    sourceRef: str
    contentMatrixSha256: Sha256
    boundarySetSha256: Sha256
    issuedAtUtc: UtcTimestamp
    expiresAtUtc: UtcTimestamp
    signerProvenance: SignerProvenance
    keyId: Sha256
    publicKeyBase64: Base64Value
    signatureBase64: Base64Value
    leaseHash: Sha256

    @field_validator("issuedAtUtc", "expiresAtUtc")
    @classmethod
    def timestamps_are_utc(cls, value: str) -> str:
        return _validate_timestamp(value)

    @field_validator("publicKeyBase64", "signatureBase64")
    @classmethod
    def base64_is_valid(cls, value: str) -> str:
        return _validate_b64(value)

    @model_validator(mode="after")
    def lease_window_and_key_are_valid(self) -> AssetLease:
        issued = datetime.fromisoformat(self.issuedAtUtc.removesuffix("Z") + "+00:00")
        expires = datetime.fromisoformat(self.expiresAtUtc.removesuffix("Z") + "+00:00")
        if expires <= issued or (expires - issued).total_seconds() > 900:
            raise ValueError("asset lease window must be positive and no longer than 900 seconds")
        public_key = base64.b64decode(self.publicKeyBase64, validate=True)
        signature = base64.b64decode(self.signatureBase64, validate=True)
        if len(public_key) != 32 or len(signature) != 64:
            raise ValueError("Ed25519 public key or signature length is invalid")
        return self


class LedgerAppendReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:ledger-append-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    validationReceiptId: Uuid36
    leaseId: Uuid36 | None
    firstSequence: int | None = Field(default=None, strict=True, ge=0)
    lastSequence: int | None = Field(default=None, strict=True, ge=0)
    chainHeadSha256: Sha256 | None
    transactionCommitted: bool
    checkpointCompleted: bool
    idempotentReplay: bool
    validationStatus: ValidationStatus
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    receiptHash: Sha256

    @model_validator(mode="after")
    def append_is_consistent(self) -> LedgerAppendReceipt:
        passed = self.transactionCommitted and self.checkpointCompleted
        if passed != (self.validationStatus is ValidationStatus.PASS):
            raise ValueError("ledger append status disagrees with persistence evidence")
        if passed and None in (self.firstSequence, self.lastSequence, self.chainHeadSha256):
            raise ValueError("successful append requires sequence and chain evidence")
        return self


class LedgerVerificationReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:ledger-verification-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    recordCount: int = Field(strict=True, ge=0)
    validationReceiptCount: int = Field(strict=True, ge=0)
    assetLeaseCount: int = Field(strict=True, ge=0)
    ledgerSealCount: int = Field(strict=True, ge=0)
    firstSequence: int | None = Field(default=None, strict=True, ge=0)
    lastSequence: int | None = Field(default=None, strict=True, ge=0)
    chainHeadSha256: Sha256
    chainValid: bool
    typedRowsValid: bool
    signaturesValid: bool
    validationStatus: ValidationStatus
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    receiptHash: Sha256

    @model_validator(mode="after")
    def verification_is_consistent(self) -> LedgerVerificationReceipt:
        passed = self.chainValid and self.typedRowsValid and self.signaturesValid
        if passed != (self.validationStatus is ValidationStatus.PASS):
            raise ValueError("ledger verification disposition is inconsistent")
        if self.recordCount == 0:
            if self.firstSequence is not None or self.lastSequence is not None:
                raise ValueError("empty ledger cannot have sequence bounds")
        elif self.firstSequence != 0 or self.lastSequence != self.recordCount - 1:
            raise ValueError("ledger sequence bounds are not contiguous")
        return self


class LedgerSeal(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:ledger-seal:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    sealId: Uuid36
    sealedAtUtc: UtcTimestamp
    recordCount: int = Field(strict=True, ge=1)
    validationReceiptCount: int = Field(strict=True, ge=1)
    assetLeaseCount: int = Field(strict=True, ge=1)
    firstSequence: int = Field(strict=True, ge=0)
    lastSequence: int = Field(strict=True, ge=0)
    chainHeadSha256: Sha256
    signerProvenance: SignerProvenance
    keyId: Sha256
    publicKeyBase64: Base64Value
    signatureBase64: Base64Value
    sealHash: Sha256

    @field_validator("sealedAtUtc")
    @classmethod
    def timestamp_is_utc(cls, value: str) -> str:
        return _validate_timestamp(value)

    @field_validator("publicKeyBase64", "signatureBase64")
    @classmethod
    def base64_is_valid(cls, value: str) -> str:
        return _validate_b64(value)

    @model_validator(mode="after")
    def seal_counts_are_consistent(self) -> LedgerSeal:
        if self.firstSequence != 0 or self.lastSequence != self.recordCount - 1:
            raise ValueError("ledger seal sequence bounds are not contiguous")
        if self.validationReceiptCount + self.assetLeaseCount != self.recordCount:
            raise ValueError("ledger seal typed counts do not cover all evidence")
        if len(base64.b64decode(self.publicKeyBase64, validate=True)) != 32:
            raise ValueError("ledger seal public key is not Ed25519")
        if len(base64.b64decode(self.signatureBase64, validate=True)) != 64:
            raise ValueError("ledger seal signature is not Ed25519")
        return self


class HookConfig(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:hook-config:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    repositoryRoot: str
    ledgerPath: str
    privateKeyPath: str
    baselineTree: str | None = "HEAD"
    leaseTtlSeconds: int = Field(default=300, strict=True, ge=1, le=900)
    signerProvenance: SignerProvenance = SignerProvenance.LOCAL_REPOSITORY_KEY


class HookExecutionReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:hook-execution-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    validationReceipt: PerimeterValidationReceipt
    assetLease: AssetLease | None
    ledgerAppendReceipt: LedgerAppendReceipt | None
    validationStatus: ValidationStatus
    exitCode: Literal[0, 1]
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    receiptHash: Sha256

    @model_validator(mode="after")
    def hook_is_consistent(self) -> HookExecutionReceipt:
        admitted = (
            self.validationReceipt.validationStatus is ValidationStatus.PASS
            and self.assetLease is not None
            and self.ledgerAppendReceipt is not None
            and self.ledgerAppendReceipt.validationStatus is ValidationStatus.PASS
        )
        if admitted != (self.validationStatus is ValidationStatus.PASS and self.exitCode == 0):
            raise ValueError("hook admission evidence is inconsistent")
        return self


class KeyGenerationReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:key-generation-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    keyId: Sha256
    created: bool
    validationStatus: Literal[ValidationStatus.PASS]
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    receiptHash: Sha256


class HookInstallReceipt(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:schema:hook-install-receipt:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    hookSha256: Sha256
    hookCreated: bool
    keyId: Sha256
    keyCreated: bool
    validationStatus: Literal[ValidationStatus.PASS]
    reasonCodes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]
    receiptHash: Sha256


class PhaseThreeBuildAuthority(StrictFrozenModel):
    schemaId: Literal["urn:scaffoldctl:evidence:phase-3-build-authority:0.3.0"]
    schemaVersion: Literal["0.3.0"]
    authorityId: Literal["scaffoldctl-phase-3-build-authority-v0.3.0"]
    authorizationRef: Literal[
        "user-directive:authorize-phase-3-planned-to-validated-sealed:2026-08-03"
    ]
    upstreamArchiveSha256: Sha256
    upstreamWheelSha256: Sha256
    submittedVerificationToken: str
    submittedTokenAccepted: Literal[False]
    tokenRejectionReason: Literal["SCF.PHASE3.UPSTREAM_TOKEN_MALFORMED"]
    authorizedScope: tuple[str, ...]
    nonclaims: tuple[str, ...]
    validationStatus: Literal[ValidationStatus.PASS]
