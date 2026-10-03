from __future__ import annotations

import base64
import os
import stat
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.integrity import (
    canonical_json_bytes,
    deterministic_id,
    hash_payload,
    parse_strict_json,
    sha256_bytes,
)
from scaffoldctl.lease import key_id, verify_asset_lease
from scaffoldctl.perimeter import verify_perimeter_receipt
from scaffoldctl.phase3_models import (
    AssetLease,
    LedgerAppendReceipt,
    LedgerSeal,
    LedgerVerificationReceipt,
    PerimeterValidationReceipt,
    SignerProvenance,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import (
    PHASE_THREE_LEDGER_SCHEMA_ID,
    PHASE_THREE_LEDGER_SCHEMA_VERSION,
    PHASE_THREE_ZERO_HASH,
    ValidationStatus,
)

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS ledger_metadata (
        metadata_key VARCHAR PRIMARY KEY,
        metadata_value VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_records (
        monotonic_sequence UBIGINT PRIMARY KEY,
        record_type VARCHAR NOT NULL CHECK (record_type IN ('validation_receipt', 'asset_lease')),
        record_id UUID NOT NULL UNIQUE,
        payload_json JSON NOT NULL,
        payload_sha256 VARCHAR NOT NULL CHECK (length(payload_sha256) = 64),
        previous_record_sha256 VARCHAR NOT NULL CHECK (length(previous_record_sha256) = 64),
        record_sha256 VARCHAR NOT NULL UNIQUE CHECK (length(record_sha256) = 64),
        recorded_at_utc VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS validation_receipts (
        receipt_id UUID PRIMARY KEY,
        evidence_sequence UBIGINT NOT NULL UNIQUE,
        receipt_hash VARCHAR NOT NULL UNIQUE CHECK (length(receipt_hash) = 64),
        validation_status VARCHAR NOT NULL CHECK (validation_status IN ('pass', 'fail', 'hold')),
        exit_code UTINYINT NOT NULL,
        source_kind VARCHAR NOT NULL CHECK (source_kind IN ('git_index', 'git_tree')),
        source_ref VARCHAR NOT NULL,
        content_matrix_sha256 VARCHAR,
        boundary_set_sha256 VARCHAR,
        payload_sha256 VARCHAR NOT NULL CHECK (length(payload_sha256) = 64),
        recorded_at_utc VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_leases (
        lease_id UUID PRIMARY KEY,
        evidence_sequence UBIGINT NOT NULL UNIQUE,
        validation_receipt_id UUID NOT NULL,
        lease_hash VARCHAR NOT NULL UNIQUE CHECK (length(lease_hash) = 64),
        purpose VARCHAR NOT NULL CHECK (purpose IN ('pre_commit', 'ci_admission')),
        key_id VARCHAR NOT NULL CHECK (length(key_id) = 64),
        issued_at_utc VARCHAR NOT NULL,
        expires_at_utc VARCHAR NOT NULL,
        signature_base64 VARCHAR NOT NULL,
        payload_sha256 VARCHAR NOT NULL CHECK (length(payload_sha256) = 64)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger_seals (
        seal_id UUID PRIMARY KEY,
        seal_hash VARCHAR NOT NULL UNIQUE CHECK (length(seal_hash) = 64),
        sealed_at_utc VARCHAR NOT NULL,
        chain_head_sha256 VARCHAR NOT NULL CHECK (length(chain_head_sha256) = 64),
        record_count UBIGINT NOT NULL,
        key_id VARCHAR NOT NULL CHECK (length(key_id) = 64),
        signature_base64 VARCHAR NOT NULL,
        payload_json JSON NOT NULL,
        payload_sha256 VARCHAR NOT NULL CHECK (length(payload_sha256) = 64)
    )
    """,
)
_DDL_SHA256 = hash_payload(tuple(" ".join(statement.split()) for statement in _DDL))


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_ledger_path(value: str | Path, *, create_parent: bool) -> Path:
    path = Path(os.path.abspath(value))
    if create_parent:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for candidate in (*reversed(path.parents), path):
        try:
            if candidate.is_symlink():
                raise PhaseThreeError(
                    ReasonCode.LEDGER_PATH_INVALID,
                    "ledger path crosses a symlink",
                    exit_code=1,
                )
        except OSError as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_PATH_INVALID,
                "ledger path cannot be inspected",
                exit_code=1,
            ) from exc
    if path.exists():
        try:
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("ledger is not a regular file")
        except (OSError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_PATH_INVALID,
                "ledger path is not a regular file",
                exit_code=1,
            ) from exc
    elif not create_parent:
        raise PhaseThreeError(
            ReasonCode.LEDGER_PATH_INVALID,
            "ledger does not exist",
            exit_code=1,
        )
    return path


def _record_hash(
    sequence: int,
    record_type: str,
    record_id: str,
    payload_sha256: str,
    previous_hash: str,
) -> str:
    return hash_payload(
        {
            "monotonicSequence": sequence,
            "payloadSha256": payload_sha256,
            "previousRecordSha256": previous_hash,
            "recordId": record_id,
            "recordType": record_type,
        }
    )


def _append_receipt(payload: dict[str, Any]) -> LedgerAppendReceipt:
    return LedgerAppendReceipt(**payload, receiptHash=hash_payload(payload))


def failed_append_receipt(
    validation_receipt_id: str,
    lease_id: str | None,
    error: BaseException,
) -> LedgerAppendReceipt:
    reason = (
        error.reason_code if isinstance(error, PhaseThreeError) else ReasonCode.LEDGER_APPEND_FAILED
    )
    payload = {
        "chainHeadSha256": None,
        "checkpointCompleted": False,
        "firstSequence": None,
        "idempotentReplay": False,
        "lastSequence": None,
        "leaseId": lease_id,
        "reasonCodes": (reason, ReasonCode.LEDGER_APPEND_FAILED),
        "schemaId": "urn:scaffoldctl:schema:ledger-append-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "transactionCommitted": False,
        "validationReceiptId": validation_receipt_id,
        "validationStatus": ValidationStatus.FAIL,
    }
    return _append_receipt(payload)


def _validate_append_inputs(
    receipt: PerimeterValidationReceipt,
    lease: AssetLease | None,
) -> None:
    verify_perimeter_receipt(receipt)
    if receipt.validationStatus is ValidationStatus.PASS and lease is None:
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_MISSING,
            "passing validation receipt requires a signed asset lease",
            exit_code=1,
        )
    if receipt.validationStatus is not ValidationStatus.PASS and lease is not None:
        raise PhaseThreeError(
            ReasonCode.PERIMETER_INVALID,
            "rejected validation receipt cannot carry an asset lease",
            exit_code=1,
        )
    if lease is None:
        return
    verify_asset_lease(lease)
    if (
        lease.validationReceiptId != receipt.receiptId
        or lease.validationReceiptHash != receipt.receiptHash
    ):
        raise PhaseThreeError(
            ReasonCode.LEASE_SIGNATURE_INVALID,
            "asset lease does not bind the supplied receipt",
            exit_code=1,
        )


def _successful_append_receipt(
    receipt: PerimeterValidationReceipt,
    lease: AssetLease | None,
    first_sequence: int,
    last_sequence: int,
    chain_head: str,
    *,
    replay: bool,
) -> LedgerAppendReceipt:
    payload = {
        "chainHeadSha256": chain_head,
        "checkpointCompleted": True,
        "firstSequence": first_sequence,
        "idempotentReplay": replay,
        "lastSequence": last_sequence,
        "leaseId": None if lease is None else lease.leaseId,
        "reasonCodes": (
            ReasonCode.LEDGER_APPEND_COMMITTED,
            ReasonCode.LEDGER_CHECKPOINT_COMPLETE,
        ),
        "schemaId": "urn:scaffoldctl:schema:ledger-append-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "transactionCommitted": True,
        "validationReceiptId": receipt.receiptId,
        "validationStatus": ValidationStatus.PASS,
    }
    return _append_receipt(payload)


def _normalized_typed_rows(rows: list[tuple[Any, ...]]) -> list[tuple[str, int, str, str]]:
    return [(str(row[0]), int(row[1]), str(row[2]), str(row[3])) for row in rows]


class DuckDbLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = _canonical_ledger_path(path, create_parent=True)

    def _connect(self, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        try:
            connection = duckdb.connect(os.fspath(self.path), read_only=read_only)
            connection.execute("SET enable_progress_bar = false")
            if not read_only:
                self._initialize_schema(connection)
            else:
                self._verify_schema(connection)
            return connection
        except PhaseThreeError:
            raise
        except (duckdb.Error, OSError) as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_SCHEMA_INVALID,
                "DuckDB ledger cannot be opened",
                exit_code=1,
            ) from exc

    @staticmethod
    def _initialize_schema(connection: duckdb.DuckDBPyConnection) -> None:
        try:
            for statement in _DDL:
                connection.execute(statement)
            rows = dict(connection.execute("SELECT * FROM ledger_metadata").fetchall())
            expected = {
                "ddl_sha256": _DDL_SHA256,
                "schema_id": PHASE_THREE_LEDGER_SCHEMA_ID,
                "schema_version": PHASE_THREE_LEDGER_SCHEMA_VERSION,
            }
            if not rows:
                connection.executemany(
                    "INSERT INTO ledger_metadata VALUES (?, ?)",
                    tuple(expected.items()),
                )
            elif rows != expected:
                raise PhaseThreeError(
                    ReasonCode.LEDGER_SCHEMA_INVALID,
                    "DuckDB ledger metadata drifted",
                    exit_code=1,
                )
        except PhaseThreeError:
            raise
        except duckdb.Error as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_SCHEMA_INVALID,
                "DuckDB ledger schema initialization failed",
                exit_code=1,
            ) from exc

    @staticmethod
    def _verify_schema(connection: duckdb.DuckDBPyConnection) -> None:
        try:
            rows = dict(connection.execute("SELECT * FROM ledger_metadata").fetchall())
        except duckdb.Error as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_SCHEMA_INVALID,
                "DuckDB ledger metadata is missing",
                exit_code=1,
            ) from exc
        expected = {
            "ddl_sha256": _DDL_SHA256,
            "schema_id": PHASE_THREE_LEDGER_SCHEMA_ID,
            "schema_version": PHASE_THREE_LEDGER_SCHEMA_VERSION,
        }
        if rows != expected:
            raise PhaseThreeError(
                ReasonCode.LEDGER_SCHEMA_INVALID,
                "DuckDB ledger metadata is invalid",
                exit_code=1,
            )

    @staticmethod
    def _tail(connection: duckdb.DuckDBPyConnection) -> tuple[int, str]:
        row = connection.execute(
            "SELECT monotonic_sequence, record_sha256 FROM evidence_records "
            "ORDER BY monotonic_sequence DESC LIMIT 1"
        ).fetchone()
        return (-1, PHASE_THREE_ZERO_HASH) if row is None else (int(row[0]), str(row[1]))

    @staticmethod
    def _append_record(
        connection: duckdb.DuckDBPyConnection,
        *,
        sequence: int,
        record_type: str,
        record_id: str,
        model: PerimeterValidationReceipt | AssetLease,
        previous_hash: str,
        recorded_at_utc: str,
    ) -> tuple[str, str]:
        payload_bytes = canonical_json_bytes(model)
        payload_sha256 = sha256_bytes(payload_bytes)
        record_sha256 = _record_hash(
            sequence,
            record_type,
            record_id,
            payload_sha256,
            previous_hash,
        )
        connection.execute(
            "INSERT INTO evidence_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence,
                record_type,
                record_id,
                payload_bytes.decode("utf-8"),
                payload_sha256,
                previous_hash,
                record_sha256,
                recorded_at_utc,
            ),
        )
        return payload_sha256, record_sha256

    @staticmethod
    def _existing_sequences(
        connection: duckdb.DuckDBPyConnection,
        receipt: PerimeterValidationReceipt,
        lease: AssetLease | None,
    ) -> tuple[int, ...] | None:
        existing = connection.execute(
            "SELECT receipt_hash, evidence_sequence FROM validation_receipts WHERE receipt_id = ?",
            (receipt.receiptId,),
        ).fetchone()
        if existing is None:
            return None
        if str(existing[0]) != receipt.receiptHash:
            raise PhaseThreeError(
                ReasonCode.LEDGER_IDENTITY_CONFLICT,
                "validation receipt identity already binds another hash",
                exit_code=1,
            )
        sequences = [int(existing[1])]
        if lease is None:
            return tuple(sequences)
        existing_lease = connection.execute(
            "SELECT lease_hash, evidence_sequence FROM asset_leases WHERE lease_id = ?",
            (lease.leaseId,),
        ).fetchone()
        if existing_lease is None or str(existing_lease[0]) != lease.leaseHash:
            raise PhaseThreeError(
                ReasonCode.LEDGER_IDENTITY_CONFLICT,
                "asset lease replay is incomplete or conflicting",
                exit_code=1,
            )
        sequences.append(int(existing_lease[1]))
        return tuple(sequences)

    def _insert_validation_row(
        self,
        connection: duckdb.DuckDBPyConnection,
        receipt: PerimeterValidationReceipt,
        sequence: int,
        previous_hash: str,
    ) -> str:
        payload_hash, record_hash = self._append_record(
            connection,
            sequence=sequence,
            record_type="validation_receipt",
            record_id=receipt.receiptId,
            model=receipt,
            previous_hash=previous_hash,
            recorded_at_utc=receipt.recordedAtUtc,
        )
        connection.execute(
            "INSERT INTO validation_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt.receiptId,
                sequence,
                receipt.receiptHash,
                receipt.validationStatus.value,
                receipt.exitCode,
                receipt.sourceKind.value,
                receipt.sourceRef,
                receipt.contentMatrixSha256,
                receipt.boundarySetSha256,
                payload_hash,
                receipt.recordedAtUtc,
            ),
        )
        return record_hash

    def _insert_lease_row(
        self,
        connection: duckdb.DuckDBPyConnection,
        lease: AssetLease,
        sequence: int,
        previous_hash: str,
    ) -> str:
        payload_hash, record_hash = self._append_record(
            connection,
            sequence=sequence,
            record_type="asset_lease",
            record_id=lease.leaseId,
            model=lease,
            previous_hash=previous_hash,
            recorded_at_utc=lease.issuedAtUtc,
        )
        connection.execute(
            "INSERT INTO asset_leases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                lease.leaseId,
                sequence,
                lease.validationReceiptId,
                lease.leaseHash,
                lease.purpose.value,
                lease.keyId,
                lease.issuedAtUtc,
                lease.expiresAtUtc,
                lease.signatureBase64,
                payload_hash,
            ),
        )
        return record_hash

    def _insert_append_rows(
        self,
        connection: duckdb.DuckDBPyConnection,
        receipt: PerimeterValidationReceipt,
        lease: AssetLease | None,
    ) -> tuple[int, int, str]:
        last_sequence, previous_hash = self._tail(connection)
        first_sequence = last_sequence + 1
        chain_head = self._insert_validation_row(
            connection, receipt, first_sequence, previous_hash
        )
        last_written = first_sequence
        if lease is not None:
            last_written += 1
            chain_head = self._insert_lease_row(connection, lease, last_written, chain_head)
        return first_sequence, last_written, chain_head

    def append_validation(
        self,
        receipt: PerimeterValidationReceipt,
        lease: AssetLease | None,
    ) -> LedgerAppendReceipt:
        _validate_append_inputs(receipt, lease)
        connection = self._connect()
        transaction_open = False
        try:
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
            sequences = self._existing_sequences(connection, receipt, lease)
            if sequences is not None:
                connection.execute("COMMIT")
                transaction_open = False
                _, chain_head = self._tail(connection)
                connection.execute("CHECKPOINT")
                return _successful_append_receipt(
                    receipt, lease, min(sequences), max(sequences), chain_head, replay=True
                )
            first_sequence, last_written, chain_head = self._insert_append_rows(
                connection, receipt, lease
            )
            connection.execute("COMMIT")
            transaction_open = False
            connection.execute("CHECKPOINT")
        except PhaseThreeError:
            if transaction_open:
                connection.execute("ROLLBACK")
            raise
        except duckdb.Error as exc:
            if transaction_open:
                with suppress(duckdb.Error):
                    connection.execute("ROLLBACK")
            raise PhaseThreeError(
                ReasonCode.LEDGER_APPEND_FAILED,
                "DuckDB validation transaction failed",
                exit_code=1,
            ) from exc
        finally:
            connection.close()
        return _successful_append_receipt(
            receipt, lease, first_sequence, last_written, chain_head, replay=False
        )

    def _read_verification_rows(
        self,
    ) -> tuple[
        list[tuple[Any, ...]],
        list[tuple[Any, ...]],
        list[tuple[Any, ...]],
        list[tuple[Any, ...]],
    ]:
        connection = self._connect(read_only=True)
        try:
            evidence = connection.execute(
                "SELECT monotonic_sequence, record_type, CAST(record_id AS VARCHAR), "
                "CAST(payload_json AS VARCHAR), payload_sha256, previous_record_sha256, "
                "record_sha256 FROM evidence_records ORDER BY monotonic_sequence"
            ).fetchall()
            validations = connection.execute(
                "SELECT CAST(receipt_id AS VARCHAR), evidence_sequence, receipt_hash, "
                "payload_sha256 FROM validation_receipts ORDER BY evidence_sequence"
            ).fetchall()
            leases = connection.execute(
                "SELECT CAST(lease_id AS VARCHAR), evidence_sequence, lease_hash, payload_sha256 "
                "FROM asset_leases ORDER BY evidence_sequence"
            ).fetchall()
            seals = connection.execute(
                "SELECT CAST(seal_id AS VARCHAR), seal_hash, chain_head_sha256, record_count, "
                "key_id, signature_base64, CAST(payload_json AS VARCHAR), payload_sha256 "
                "FROM ledger_seals ORDER BY sealed_at_utc, seal_id"
            ).fetchall()
            return evidence, validations, leases, seals
        except duckdb.Error as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_CHAIN_INVALID,
                "DuckDB ledger rows cannot be read",
                exit_code=1,
            ) from exc
        finally:
            connection.close()

    @staticmethod
    def _verify_evidence_row(
        row: tuple[Any, ...],
        expected_sequence: int,
        previous_hash: str,
    ) -> tuple[str, tuple[str, int, str, str] | None, tuple[str, int, str, str] | None]:
        sequence = int(row[0])
        record_type = str(row[1])
        record_id = str(row[2])
        payload_bytes = str(row[3]).encode("utf-8")
        payload_sha256 = str(row[4])
        observed_previous = str(row[5])
        record_sha256 = str(row[6])
        expected_hash = _record_hash(
            sequence, record_type, record_id, payload_sha256, observed_previous
        )
        if (
            sequence != expected_sequence
            or observed_previous != previous_hash
            or sha256_bytes(payload_bytes) != payload_sha256
            or expected_hash != record_sha256
            or canonical_json_bytes(parse_strict_json(payload_bytes)) != payload_bytes
        ):
            raise ValueError("evidence chain mismatch")
        validation_row = None
        lease_row = None
        if record_type == "validation_receipt":
            model = PerimeterValidationReceipt.model_validate_json(payload_bytes)
            verify_perimeter_receipt(model)
            if model.receiptId != record_id:
                raise ValueError("validation receipt identity mismatch")
            validation_row = (record_id, sequence, model.receiptHash, payload_sha256)
        elif record_type == "asset_lease":
            lease = AssetLease.model_validate_json(payload_bytes)
            verify_asset_lease(lease)
            if lease.leaseId != record_id:
                raise ValueError("asset lease identity mismatch")
            lease_row = (record_id, sequence, lease.leaseHash, payload_sha256)
        else:
            raise ValueError("unknown evidence record type")
        return record_sha256, validation_row, lease_row

    @classmethod
    def _verify_evidence_rows(
        cls,
        evidence: list[tuple[Any, ...]],
    ) -> tuple[str, list[tuple[str, int, str, str]], list[tuple[str, int, str, str]]]:
        previous_hash = PHASE_THREE_ZERO_HASH
        validations: list[tuple[str, int, str, str]] = []
        leases: list[tuple[str, int, str, str]] = []
        try:
            for expected_sequence, row in enumerate(evidence):
                previous_hash, validation, lease = cls._verify_evidence_row(
                    row, expected_sequence, previous_hash
                )
                if validation is not None:
                    validations.append(validation)
                if lease is not None:
                    leases.append(lease)
        except (PhaseThreeError, ValidationError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_CHAIN_INVALID,
                "DuckDB evidence chain verification failed",
                exit_code=1,
            ) from exc
        return previous_hash, validations, leases

    @staticmethod
    def _verify_typed_rows(
        validations: list[tuple[str, int, str, str]],
        leases: list[tuple[str, int, str, str]],
        typed_validations: list[tuple[Any, ...]],
        typed_leases: list[tuple[Any, ...]],
    ) -> None:
        if (
            validations != _normalized_typed_rows(typed_validations)
            or leases != _normalized_typed_rows(typed_leases)
        ):
            raise PhaseThreeError(
                ReasonCode.LEDGER_TYPED_ROWS_INVALID,
                "DuckDB typed rows do not match evidence records",
                exit_code=1,
            )

    @staticmethod
    def _verify_seal_row(
        row: tuple[Any, ...],
        evidence: list[tuple[Any, ...]],
    ) -> None:
        payload_bytes = str(row[6]).encode("utf-8")
        if (
            canonical_json_bytes(parse_strict_json(payload_bytes)) != payload_bytes
            or sha256_bytes(payload_bytes) != str(row[7])
        ):
            raise ValueError("ledger seal payload is not canonical")
        seal = LedgerSeal.model_validate_json(payload_bytes)
        verify_ledger_seal(seal)
        if (
            seal.sealId != str(row[0])
            or seal.sealHash != str(row[1])
            or seal.chainHeadSha256 != str(row[2])
            or seal.recordCount != int(row[3])
            or seal.keyId != str(row[4])
            or seal.signatureBase64 != str(row[5])
            or seal.lastSequence >= len(evidence)
            or seal.chainHeadSha256 != str(evidence[seal.lastSequence][6])
        ):
            raise ValueError("ledger seal typed row is inconsistent")
        prefix = evidence[: seal.lastSequence + 1]
        validations = sum(str(item[1]) == "validation_receipt" for item in prefix)
        leases = sum(str(item[1]) == "asset_lease" for item in prefix)
        if seal.validationReceiptCount != validations or seal.assetLeaseCount != leases:
            raise ValueError("ledger seal counts are inconsistent")

    @classmethod
    def _verify_seals(
        cls,
        seals: list[tuple[Any, ...]],
        evidence: list[tuple[Any, ...]],
    ) -> None:
        try:
            for row in seals:
                cls._verify_seal_row(row, evidence)
        except (PhaseThreeError, ValidationError, ValueError) as exc:
            raise PhaseThreeError(
                ReasonCode.LEDGER_SEAL_INVALID,
                "DuckDB ledger seal verification failed",
                exit_code=1,
            ) from exc

    @staticmethod
    def _verification_receipt(
        evidence: list[tuple[Any, ...]],
        validations: list[tuple[str, int, str, str]],
        leases: list[tuple[str, int, str, str]],
        seals: list[tuple[Any, ...]],
        chain_head: str,
    ) -> LedgerVerificationReceipt:
        payload = {
            "assetLeaseCount": len(leases),
            "chainHeadSha256": chain_head,
            "chainValid": True,
            "firstSequence": 0 if evidence else None,
            "lastSequence": len(evidence) - 1 if evidence else None,
            "ledgerSealCount": len(seals),
            "reasonCodes": (
                ReasonCode.LEDGER_CHAIN_VALID,
                ReasonCode.LEDGER_REPLAY_VERIFIED,
            ),
            "recordCount": len(evidence),
            "schemaId": "urn:scaffoldctl:schema:ledger-verification-receipt:0.3.0",
            "schemaVersion": "0.3.0",
            "signaturesValid": True,
            "typedRowsValid": True,
            "validationReceiptCount": len(validations),
            "validationStatus": ValidationStatus.PASS,
        }
        return LedgerVerificationReceipt(**payload, receiptHash=hash_payload(payload))

    def verify(self) -> LedgerVerificationReceipt:
        evidence, typed_validations, typed_leases, seals = self._read_verification_rows()
        chain_head, validations, leases = self._verify_evidence_rows(evidence)
        self._verify_typed_rows(validations, leases, typed_validations, typed_leases)
        self._verify_seals(seals, evidence)
        return self._verification_receipt(evidence, validations, leases, seals, chain_head)

    def seal(
        self,
        key: Ed25519PrivateKey,
        provenance: SignerProvenance,
        *,
        now: datetime | None = None,
    ) -> LedgerSeal:
        verification = self.verify()
        if (
            verification.recordCount < 1
            or verification.validationReceiptCount < 1
            or verification.assetLeaseCount < 1
            or verification.firstSequence is None
            or verification.lastSequence is None
        ):
            raise PhaseThreeError(
                ReasonCode.LEDGER_SEAL_INVALID,
                "ledger lacks validation and lease evidence",
                exit_code=1,
            )
        observed = now.astimezone(UTC) if now is not None else datetime.now(UTC)
        public_key = key.public_key().public_bytes_raw()
        unsigned = {
            "assetLeaseCount": verification.assetLeaseCount,
            "chainHeadSha256": verification.chainHeadSha256,
            "firstSequence": verification.firstSequence,
            "keyId": key_id(key),
            "lastSequence": verification.lastSequence,
            "publicKeyBase64": base64.b64encode(public_key).decode("ascii"),
            "recordCount": verification.recordCount,
            "schemaId": "urn:scaffoldctl:schema:ledger-seal:0.3.0",
            "schemaVersion": "0.3.0",
            "sealedAtUtc": _timestamp(observed),
            "signerProvenance": provenance,
            "validationReceiptCount": verification.validationReceiptCount,
        }
        seal_id = deterministic_id("duckdb-ledger-seal", hash_payload(unsigned))
        signed_payload = {**unsigned, "sealId": seal_id}
        signature = key.sign(canonical_json_bytes(signed_payload))
        payload = {
            **signed_payload,
            "signatureBase64": base64.b64encode(signature).decode("ascii"),
        }
        seal = LedgerSeal(**payload, sealHash=hash_payload(payload))
        self._append_seal(seal)
        return seal

    def _append_seal(self, seal: LedgerSeal) -> None:
        verify_ledger_seal(seal)
        connection = self._connect()
        transaction_open = False
        try:
            connection.execute("BEGIN TRANSACTION")
            transaction_open = True
            existing = connection.execute(
                "SELECT seal_hash FROM ledger_seals WHERE seal_id = ?",
                (seal.sealId,),
            ).fetchone()
            if existing is not None:
                if str(existing[0]) != seal.sealHash:
                    raise PhaseThreeError(
                        ReasonCode.LEDGER_IDENTITY_CONFLICT,
                        "ledger seal identity conflict",
                        exit_code=1,
                    )
            else:
                payload_bytes = canonical_json_bytes(seal)
                connection.execute(
                    "INSERT INTO ledger_seals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        seal.sealId,
                        seal.sealHash,
                        seal.sealedAtUtc,
                        seal.chainHeadSha256,
                        seal.recordCount,
                        seal.keyId,
                        seal.signatureBase64,
                        payload_bytes.decode("utf-8"),
                        sha256_bytes(payload_bytes),
                    ),
                )
            connection.execute("COMMIT")
            transaction_open = False
            connection.execute("CHECKPOINT")
        except PhaseThreeError:
            if transaction_open:
                connection.execute("ROLLBACK")
            raise
        except duckdb.Error as exc:
            if transaction_open:
                with suppress(duckdb.Error):
                    connection.execute("ROLLBACK")
            raise PhaseThreeError(
                ReasonCode.LEDGER_SEAL_INVALID,
                "DuckDB ledger seal transaction failed",
                exit_code=1,
            ) from exc
        finally:
            connection.close()


def verify_ledger_seal(seal: LedgerSeal) -> None:
    payload = seal.model_dump(mode="python")
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"sealId", "signatureBase64", "sealHash"}
    }
    expected_id = deterministic_id("duckdb-ledger-seal", hash_payload(unsigned))
    signed_payload = {**unsigned, "sealId": seal.sealId}
    signature_payload = {**signed_payload, "signatureBase64": seal.signatureBase64}
    public_key = base64.b64decode(seal.publicKeyBase64, validate=True)
    if (
        seal.sealId != expected_id
        or seal.sealHash != hash_payload(signature_payload)
        or seal.keyId != sha256_bytes(public_key)
    ):
        raise PhaseThreeError(
            ReasonCode.LEDGER_SEAL_INVALID,
            "ledger seal identity or hash is invalid",
            exit_code=1,
        )
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            base64.b64decode(seal.signatureBase64, validate=True),
            canonical_json_bytes(signed_payload),
        )
    except (InvalidSignature, ValueError) as exc:
        raise PhaseThreeError(
            ReasonCode.LEDGER_SEAL_INVALID,
            "ledger seal signature is invalid",
            exit_code=1,
        ) from exc
