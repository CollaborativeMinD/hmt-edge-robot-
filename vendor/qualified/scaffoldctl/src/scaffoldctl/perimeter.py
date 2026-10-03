from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import PurePosixPath

from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import GitObjectSnapshot, GitRepository
from scaffoldctl.integrity import hash_payload, stamp_payload, verify_stamped_payload
from scaffoldctl.phase3_models import (
    BoundaryValidationRecord,
    GitSnapshotSource,
    PerimeterOperation,
    PerimeterValidationReceipt,
)
from scaffoldctl.policy import load_policy_pack
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus
from scaffoldctl.validation import validate_boundary


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _unique(values: Iterable[ReasonCode]) -> tuple[ReasonCode, ...]:
    result: list[ReasonCode] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def discover_boundaries(
    snapshot: GitObjectSnapshot,
    baseline: GitObjectSnapshot | None = None,
) -> tuple[str, ...]:
    policy_name = load_policy_pack().policyFileName
    targets = {"."}
    for source in (snapshot, baseline):
        if source is None:
            continue
        for entry in source.matrix.entries:
            path = PurePosixPath(entry.relativePath)
            if path.name == policy_name:
                targets.add(path.parent.as_posix())
    return tuple(sorted(targets, key=lambda value: value.encode("utf-8")))


def _stamp_receipt(payload: dict[str, object]) -> PerimeterValidationReceipt:
    stamped = stamp_payload(
        payload,
        kind="perimeter-validation-receipt",
        id_field="receiptId",
        hash_field="receiptHash",
    )
    try:
        return PerimeterValidationReceipt.model_validate(stamped)
    except ValidationError as exc:
        raise PhaseThreeError(
            ReasonCode.SCHEMA_INVALID,
            "perimeter receipt schema validation failed",
            exit_code=1,
        ) from exc


def verify_perimeter_receipt(receipt: PerimeterValidationReceipt) -> None:
    if not verify_stamped_payload(
        receipt.model_dump(mode="json"),
        kind="perimeter-validation-receipt",
        id_field="receiptId",
        hash_field="receiptHash",
    ):
        raise PhaseThreeError(
            ReasonCode.RECEIPT_HASH_INVALID,
            "perimeter receipt identity or hash is invalid",
            exit_code=1,
        )


def failure_perimeter_receipt(
    operation: PerimeterOperation,
    source_kind: GitSnapshotSource,
    source_ref: str,
    error: BaseException,
) -> PerimeterValidationReceipt:
    reason = error.reason_code if isinstance(error, PhaseThreeError) else ReasonCode.INTERNAL_ERROR
    source_invalid = (
        ReasonCode.GIT_INDEX_INVALID
        if source_kind is GitSnapshotSource.INDEX
        else ReasonCode.GIT_TREE_INVALID
    )
    return _stamp_receipt(
        {
            "baselineContentMatrixSha256": None,
            "boundaries": (),
            "boundarySetSha256": None,
            "contentMatrixSha256": None,
            "exitCode": 1,
            "matrixSha256": None,
            "operation": operation,
            "reasonCodes": _unique((reason, source_invalid, ReasonCode.PERIMETER_INVALID)),
            "recordedAtUtc": utc_now(),
            "schemaId": "urn:scaffoldctl:schema:perimeter-validation-receipt:0.3.0",
            "schemaVersion": "0.3.0",
            "sourceKind": source_kind,
            "sourceRef": source_ref,
            "validationStatus": ValidationStatus.FAIL,
        }
    )


def _boundary_records(
    snapshot: GitObjectSnapshot,
    baseline: GitObjectSnapshot | None,
    source_valid: ReasonCode,
    source_invalid: ReasonCode,
) -> tuple[tuple[str, ...], tuple[BoundaryValidationRecord, ...]]:
    targets = discover_boundaries(snapshot, baseline)
    records: list[BoundaryValidationRecord] = []
    for target in targets:
        outcome = validate_boundary(
            snapshot,
            target,
            snapshot_valid_reason=source_valid,
            snapshot_invalid_reason=source_invalid,
        )
        status = ValidationStatus.PASS if outcome.admitted else ValidationStatus.FAIL
        records.append(
            BoundaryValidationRecord(
                targetPath=target,
                validationStatus=status,
                admitted=outcome.admitted,
                reasonCodes=outcome.reason_codes,
                findings=outcome.findings,
                artifacts=outcome.artifacts,
            )
        )
    return targets, tuple(records)


def _perimeter_reasons(
    records: tuple[BoundaryValidationRecord, ...],
    source_valid: ReasonCode,
    source_invalid: ReasonCode,
) -> tuple[ReasonCode, ...]:
    if records and all(record.admitted for record in records):
        return (ReasonCode.BOUNDARY_DISCOVERY_VALID, source_valid, ReasonCode.PERIMETER_VALID)
    nested = tuple(reason for record in records for reason in record.reasonCodes)
    return _unique((*nested, source_invalid, ReasonCode.PERIMETER_INVALID))


def validate_snapshot(
    snapshot: GitObjectSnapshot,
    operation: PerimeterOperation,
    *,
    baseline: GitObjectSnapshot | None = None,
) -> PerimeterValidationReceipt:
    source_valid = (
        ReasonCode.GIT_INDEX_VALID
        if snapshot.matrix.sourceKind is GitSnapshotSource.INDEX
        else ReasonCode.GIT_TREE_VALID
    )
    source_invalid = (
        ReasonCode.GIT_INDEX_INVALID
        if snapshot.matrix.sourceKind is GitSnapshotSource.INDEX
        else ReasonCode.GIT_TREE_INVALID
    )
    targets, records = _boundary_records(snapshot, baseline, source_valid, source_invalid)
    admitted = bool(records) and all(record.admitted for record in records)
    reasons = _perimeter_reasons(records, source_valid, source_invalid)
    return _stamp_receipt(
        {
            "baselineContentMatrixSha256": (
                None if baseline is None else baseline.matrix.contentMatrixSha256
            ),
            "boundaries": tuple(records),
            "boundarySetSha256": hash_payload(targets),
            "contentMatrixSha256": snapshot.matrix.contentMatrixSha256,
            "exitCode": 0 if admitted else 1,
            "matrixSha256": snapshot.matrix.matrixSha256,
            "operation": operation,
            "reasonCodes": reasons,
            "recordedAtUtc": utc_now(),
            "schemaId": "urn:scaffoldctl:schema:perimeter-validation-receipt:0.3.0",
            "schemaVersion": "0.3.0",
            "sourceKind": snapshot.matrix.sourceKind,
            "sourceRef": snapshot.matrix.sourceRef,
            "validationStatus": ValidationStatus.PASS if admitted else ValidationStatus.FAIL,
        }
    )


def validate_index_snapshot(
    repository: GitRepository,
    *,
    baseline: GitObjectSnapshot | None = None,
) -> PerimeterValidationReceipt:
    start = repository.capture_index_matrix()
    snapshot = GitObjectSnapshot(repository, start)
    receipt = validate_snapshot(
        snapshot,
        PerimeterOperation.VALIDATE_STAGED,
        baseline=baseline,
    )
    end = repository.capture_index_matrix()
    if start.matrixSha256 == end.matrixSha256:
        return receipt
    return _stamp_receipt(
        {
            **{
                key: value
                for key, value in receipt.model_dump(mode="python").items()
                if key not in {"receiptId", "receiptHash"}
            },
            "exitCode": 1,
            "reasonCodes": _unique(
                (
                    *receipt.reasonCodes,
                    ReasonCode.GIT_INDEX_CHANGED,
                    ReasonCode.GIT_INDEX_INVALID,
                    ReasonCode.PERIMETER_INVALID,
                )
            ),
            "validationStatus": ValidationStatus.FAIL,
        }
    )
