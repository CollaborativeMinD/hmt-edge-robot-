from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from phase3_support import git, init_repository
from pydantic import ValidationError

import scaffoldctl.lease as lease_module
from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import GitRepository
from scaffoldctl.integrity import canonical_json_bytes, deterministic_id, hash_payload, sha256_bytes
from scaffoldctl.lease import (
    generate_keypair,
    key_id,
    load_private_key,
    sign_asset_lease,
    verify_asset_lease,
)
from scaffoldctl.ledger import (
    DuckDbLedger,
    _canonical_ledger_path,
    _record_hash,
    failed_append_receipt,
    verify_ledger_seal,
)
from scaffoldctl.perimeter import validate_index_snapshot
from scaffoldctl.phase3_models import (
    AssetLease,
    GitSnapshotSource,
    LeasePurpose,
    SignerProvenance,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus


def _validation_and_key(tmp_path: Path) -> tuple[object, Ed25519PrivateKey, Path, Path]:
    root = tmp_path / "repo"
    init_repository(root)
    receipt = validate_index_snapshot(GitRepository(root))
    private = tmp_path / "key" / "private.pem"
    public = tmp_path / "key" / "public.pem"
    observed, created = generate_keypair(private, public)
    key = load_private_key(private)
    assert created is True
    assert observed == key_id(key)
    return receipt, key, private, public


def _lease(receipt: object, key: Ed25519PrivateKey, now: datetime | None = None) -> AssetLease:
    return sign_asset_lease(
        receipt,  # type: ignore[arg-type]
        key,
        LeasePurpose.PRE_COMMIT,
        SignerProvenance.LOCAL_REPOSITORY_KEY,
        now=now,
    )


def test_key_generation_preserves_matching_pair_and_permissions(tmp_path: Path) -> None:
    _, key, private, public = _validation_and_key(tmp_path)
    private_bytes = private.read_bytes()
    observed, created = generate_keypair(private, public)
    assert created is False
    assert observed == key_id(key)
    assert private.read_bytes() == private_bytes
    assert private.stat().st_mode & 0o777 == 0o600
    assert public.stat().st_mode & 0o777 == 0o644


def test_key_generation_rejects_orphan_mismatch_and_symlink(tmp_path: Path) -> None:
    orphan = tmp_path / "orphan.pub"
    orphan.write_text("occupied")
    with pytest.raises(PhaseThreeError):
        generate_keypair(tmp_path / "missing.pem", orphan)
    first_private = tmp_path / "first.pem"
    first_public = tmp_path / "first.pub"
    second_private = tmp_path / "second.pem"
    second_public = tmp_path / "second.pub"
    generate_keypair(first_private, first_public)
    generate_keypair(second_private, second_public)
    first_public.write_bytes(second_public.read_bytes())
    with pytest.raises(PhaseThreeError) as raised:
        generate_keypair(first_private, first_public)
    assert raised.value.reason_code is ReasonCode.LEASE_KEY_INVALID
    link = tmp_path / "linked.pem"
    link.symlink_to(first_private)
    with pytest.raises(PhaseThreeError):
        load_private_key(link)


def test_key_loading_and_generation_reject_wrong_types_and_restore_public_key(
    tmp_path: Path,
) -> None:
    same = tmp_path / "same.pem"
    with pytest.raises(PhaseThreeError):
        generate_keypair(same, same)
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    generate_keypair(private, public)
    public.unlink()
    observed, created = generate_keypair(private, public)
    assert created is False and observed == key_id(load_private_key(private)) and public.is_file()
    public.write_text("not a public key")
    with pytest.raises(PhaseThreeError):
        generate_keypair(private, public)
    oversized = tmp_path / "oversized.pem"
    oversized.write_bytes(b"x" * 4097)
    with pytest.raises(PhaseThreeError):
        load_private_key(oversized)
    rsa = generate_private_key(public_exponent=65537, key_size=2048)
    rsa_path = tmp_path / "rsa.pem"
    rsa_path.write_bytes(
        rsa.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    with pytest.raises(PhaseThreeError):
        load_private_key(rsa_path)


def test_keypair_publication_failure_rolls_back_only_owned_private_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    original = lease_module._exclusive_write
    calls = 0

    def fail_second(path: Path, data: bytes, mode: int) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected public-key failure")
        return original(path, data, mode)

    monkeypatch.setattr(lease_module, "_exclusive_write", fail_second)
    with pytest.raises(OSError):
        generate_keypair(private, public)
    assert not private.exists() and not public.exists()


def test_asset_lease_signature_identity_and_expiry(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    now = datetime(2026, 8, 3, tzinfo=UTC)
    lease = _lease(receipt, key, now)
    verify_asset_lease(lease, now=now, enforce_not_expired=True)
    verify_asset_lease(lease, now=now + timedelta(seconds=299), enforce_not_expired=True)
    with pytest.raises(PhaseThreeError) as raised:
        verify_asset_lease(lease, now=now + timedelta(seconds=300), enforce_not_expired=True)
    assert raised.value.reason_code is ReasonCode.LEASE_EXPIRED
    assert len(base64.b64decode(lease.signatureBase64)) == 64


def test_asset_lease_rejects_tampering_and_invalid_lifetime(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    lease = _lease(receipt, key)
    altered = AssetLease.model_validate(
        {
            **lease.model_dump(mode="python"),
            "sourceRef": "ALTERED",
        }
    )
    with pytest.raises(PhaseThreeError) as raised:
        verify_asset_lease(altered)
    assert raised.value.reason_code is ReasonCode.LEASE_SIGNATURE_INVALID
    for value in (0, 901, True, 1.5):
        with pytest.raises(PhaseThreeError):
            sign_asset_lease(
                receipt,  # type: ignore[arg-type]
                key,
                LeasePurpose.PRE_COMMIT,
                SignerProvenance.LOCAL_REPOSITORY_KEY,
                ttl_seconds=value,  # type: ignore[arg-type]
            )


def test_asset_lease_verifier_distinguishes_key_and_signature_tamper(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    lease = _lease(receipt, key)
    signature = bytearray(base64.b64decode(lease.signatureBase64))
    signature[0] ^= 1
    changed_signature = base64.b64encode(signature).decode()
    signature_payload = {
        **lease.model_dump(mode="python"),
        "signatureBase64": changed_signature,
    }
    signature_payload["leaseHash"] = hash_payload(
        {name: value for name, value in signature_payload.items() if name != "leaseHash"}
    )
    with pytest.raises(PhaseThreeError) as raised:
        verify_asset_lease(AssetLease.model_validate(signature_payload))
    assert raised.value.reason_code is ReasonCode.LEASE_SIGNATURE_INVALID

    unsigned = {
        name: value
        for name, value in lease.model_dump(mode="python").items()
        if name not in {"leaseId", "signatureBase64", "leaseHash"}
    }
    unsigned["keyId"] = "0" * 64
    lease_id = deterministic_id("signed-asset-lease", hash_payload(unsigned))
    signed = {**unsigned, "leaseId": lease_id}
    payload = {
        **signed,
        "signatureBase64": base64.b64encode(key.sign(canonical_json_bytes(signed))).decode(),
    }
    forged_key_id = AssetLease(**payload, leaseHash=hash_payload(payload))
    with pytest.raises(PhaseThreeError) as raised:
        verify_asset_lease(forged_key_id)
    assert raised.value.reason_code is ReasonCode.LEASE_SIGNATURE_INVALID


def test_rejected_perimeter_cannot_receive_lease(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    root.joinpath("Index.md").unlink()
    git(root, "add", "--all")
    receipt = validate_index_snapshot(GitRepository(root))
    assert receipt.validationStatus is ValidationStatus.FAIL
    with pytest.raises(PhaseThreeError) as raised:
        sign_asset_lease(
            receipt,
            Ed25519PrivateKey.generate(),
            LeasePurpose.PRE_COMMIT,
            SignerProvenance.LOCAL_REPOSITORY_KEY,
        )
    assert raised.value.reason_code is ReasonCode.PERIMETER_INVALID


def test_duckdb_append_replay_and_seal(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    lease = _lease(receipt, key)
    ledger_path = tmp_path / "evidence" / "ledger.duckdb"
    ledger = DuckDbLedger(ledger_path)
    append = ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    assert append.transactionCommitted is True
    assert append.checkpointCompleted is True
    assert append.firstSequence == 0
    assert append.lastSequence == 1
    replay = ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    assert replay.idempotentReplay is True
    assert replay.chainHeadSha256 == append.chainHeadSha256
    verification = ledger.verify()
    assert verification.recordCount == 2
    assert verification.validationReceiptCount == 1
    assert verification.assetLeaseCount == 1
    assert verification.ledgerSealCount == 0
    seal = ledger.seal(key, SignerProvenance.RELEASE_KEY)
    verify_ledger_seal(seal)
    sealed = ledger.verify()
    assert sealed.ledgerSealCount == 1
    assert sealed.chainHeadSha256 == seal.chainHeadSha256
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }
        assert {
            "asset_leases",
            "evidence_records",
            "ledger_metadata",
            "ledger_seals",
            "validation_receipts",
        } <= tables
    finally:
        connection.close()


def test_failed_validation_is_natively_persisted_without_lease(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    root.joinpath("Index.md").unlink()
    git(root, "add", "--all")
    receipt = validate_index_snapshot(GitRepository(root))
    ledger = DuckDbLedger(tmp_path / "failure.duckdb")
    append = ledger.append_validation(receipt, None)
    assert append.firstSequence == append.lastSequence == 0
    verification = ledger.verify()
    assert verification.validationReceiptCount == 1
    assert verification.assetLeaseCount == 0
    with pytest.raises(PhaseThreeError):
        ledger.seal(Ed25519PrivateKey.generate(), SignerProvenance.RELEASE_KEY)


def test_passing_validation_requires_lease_and_matching_binding(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    ledger = DuckDbLedger(tmp_path / "ledger.duckdb")
    with pytest.raises(PhaseThreeError) as raised:
        ledger.append_validation(receipt, None)  # type: ignore[arg-type]
    assert raised.value.reason_code is ReasonCode.LEASE_KEY_MISSING
    lease = _lease(receipt, key)
    altered = AssetLease.model_validate(
        {
            **lease.model_dump(mode="python"),
            "validationReceiptHash": "0" * 64,
            "leaseHash": hash_payload(
                {
                    key: value
                    for key, value in lease.model_dump(mode="python").items()
                    if key != "leaseHash"
                }
            ),
        }
    )
    with pytest.raises(PhaseThreeError):
        ledger.append_validation(receipt, altered)  # type: ignore[arg-type]


def test_ledger_chain_tamper_is_detected(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    ledger_path = tmp_path / "ledger.duckdb"
    ledger = DuckDbLedger(ledger_path)
    ledger.append_validation(receipt, _lease(receipt, key))  # type: ignore[arg-type]
    connection = duckdb.connect(str(ledger_path))
    try:
        connection.execute(
            "UPDATE evidence_records SET payload_sha256 = ? WHERE monotonic_sequence = 0",
            ("0" * 64,),
        )
    finally:
        connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_CHAIN_INVALID


def test_ledger_typed_row_and_seal_tamper_are_detected(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    ledger_path = tmp_path / "typed.duckdb"
    ledger = DuckDbLedger(ledger_path)
    lease = _lease(receipt, key)
    ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    ledger.seal(key, SignerProvenance.RELEASE_KEY)
    connection = duckdb.connect(str(ledger_path))
    try:
        connection.execute("UPDATE ledger_seals SET payload_sha256 = ?", ("0" * 64,))
    finally:
        connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_SEAL_INVALID


def test_ledger_metadata_and_path_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "ledger.duckdb"
    ledger = DuckDbLedger(path)
    connection = ledger._connect()
    connection.close()
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            "UPDATE ledger_metadata SET metadata_value = 'drift' WHERE metadata_key = 'schema_id'"
        )
    finally:
        connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_SCHEMA_INVALID
    target = tmp_path / "target.duckdb"
    target.touch()
    link = tmp_path / "link.duckdb"
    link.symlink_to(target)
    with pytest.raises(PhaseThreeError) as raised:
        DuckDbLedger(link)
    assert raised.value.reason_code is ReasonCode.LEDGER_PATH_INVALID


def test_ledger_path_schema_and_read_failures_are_distinct(tmp_path: Path) -> None:
    directory = tmp_path / "directory.duckdb"
    directory.mkdir()
    with pytest.raises(PhaseThreeError) as raised:
        DuckDbLedger(directory)
    assert raised.value.reason_code is ReasonCode.LEDGER_PATH_INVALID
    with pytest.raises(PhaseThreeError):
        _canonical_ledger_path(tmp_path / "missing.duckdb", create_parent=False)
    empty = tmp_path / "empty.duckdb"
    connection = duckdb.connect(str(empty))
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        DuckDbLedger(empty).verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_SCHEMA_INVALID
    initialized = tmp_path / "initialized.duckdb"
    ledger = DuckDbLedger(initialized)
    connection = ledger._connect()
    connection.close()
    connection = duckdb.connect(str(initialized))
    connection.execute("UPDATE ledger_metadata SET metadata_value = 'drift'")
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger._connect()
    assert raised.value.reason_code is ReasonCode.LEDGER_SCHEMA_INVALID


def test_ledger_rejects_invalid_lease_dispositions_and_bindings(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    root = tmp_path / "invalid-repo"
    init_repository(root)
    root.joinpath("Index.md").unlink()
    git(root, "add", "--all")
    rejected = validate_index_snapshot(GitRepository(root))
    ledger = DuckDbLedger(tmp_path / "binding.duckdb")
    with pytest.raises(PhaseThreeError):
        ledger.append_validation(rejected, _lease(receipt, key))  # type: ignore[arg-type]
    second = validate_index_snapshot(GitRepository(tmp_path / "repo"))
    assert second.receiptId != receipt.receiptId  # type: ignore[attr-defined]
    with pytest.raises(PhaseThreeError) as raised:
        ledger.append_validation(second, _lease(receipt, key))  # type: ignore[arg-type]
    assert raised.value.reason_code is ReasonCode.LEASE_SIGNATURE_INVALID


def test_ledger_replay_identity_and_completeness_conflicts(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    lease = _lease(receipt, key)
    path = tmp_path / "conflict.duckdb"
    ledger = DuckDbLedger(path)
    ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    connection = duckdb.connect(str(path))
    connection.execute(
        "UPDATE validation_receipts SET receipt_hash = ? WHERE receipt_id = ?",
        ("0" * 64, receipt.receiptId),  # type: ignore[attr-defined]
    )
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    assert raised.value.reason_code is ReasonCode.LEDGER_IDENTITY_CONFLICT
    connection = duckdb.connect(str(path))
    connection.execute(
        "UPDATE validation_receipts SET receipt_hash = ? WHERE receipt_id = ?",
        (receipt.receiptHash, receipt.receiptId),  # type: ignore[attr-defined]
    )
    connection.execute("DELETE FROM asset_leases")
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.append_validation(receipt, lease)  # type: ignore[arg-type]
    assert raised.value.reason_code is ReasonCode.LEDGER_IDENTITY_CONFLICT


def test_ledger_typed_rows_and_semantic_payload_tamper_are_detected(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    path = tmp_path / "typed-tamper.duckdb"
    ledger = DuckDbLedger(path)
    ledger.append_validation(receipt, _lease(receipt, key))  # type: ignore[arg-type]
    connection = duckdb.connect(str(path))
    connection.execute("UPDATE validation_receipts SET payload_sha256 = ?", ("0" * 64,))
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger.verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_TYPED_ROWS_INVALID

    semantic_path = tmp_path / "semantic-tamper.duckdb"
    semantic = DuckDbLedger(semantic_path)
    semantic.append_validation(receipt, _lease(receipt, key))  # type: ignore[arg-type]
    connection = duckdb.connect(str(semantic_path))
    row = connection.execute(
        "SELECT CAST(payload_json AS VARCHAR), CAST(record_id AS VARCHAR) "
        "FROM evidence_records WHERE monotonic_sequence = 0"
    ).fetchone()
    assert row is not None
    payload = json.loads(row[0])
    payload["exitCode"] = 0 if payload["exitCode"] == 1 else 1
    payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    payload_hash = sha256_bytes(payload_text.encode())
    record_hash = _record_hash(0, "validation_receipt", row[1], payload_hash, "0" * 64)
    connection.execute(
        "UPDATE evidence_records SET payload_json = ?, payload_sha256 = ?, record_sha256 = ? "
        "WHERE monotonic_sequence = 0",
        (payload_text, payload_hash, record_hash),
    )
    connection.execute(
        "UPDATE evidence_records SET previous_record_sha256 = ? WHERE monotonic_sequence = 1",
        (record_hash,),
    )
    lease_row = connection.execute(
        "SELECT record_type, CAST(record_id AS VARCHAR), payload_sha256 "
        "FROM evidence_records WHERE monotonic_sequence = 1"
    ).fetchone()
    assert lease_row is not None
    next_hash = _record_hash(1, lease_row[0], lease_row[1], lease_row[2], record_hash)
    connection.execute(
        "UPDATE evidence_records SET record_sha256 = ? WHERE monotonic_sequence = 1", (next_hash,)
    )
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        semantic.verify()
    assert raised.value.reason_code is ReasonCode.LEDGER_CHAIN_INVALID


def test_seal_identity_signature_and_database_conflicts_are_detected(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    path = tmp_path / "seal-conflict.duckdb"
    ledger = DuckDbLedger(path)
    ledger.append_validation(receipt, _lease(receipt, key))  # type: ignore[arg-type]
    seal = ledger.seal(key, SignerProvenance.RELEASE_KEY)
    with pytest.raises(PhaseThreeError):
        verify_ledger_seal(
            type(seal).model_validate({**seal.model_dump(mode="python"), "sealHash": "0" * 64})
        )
    signature = bytearray(base64.b64decode(seal.signatureBase64))
    signature[0] ^= 1
    changed_signature = base64.b64encode(signature).decode()
    signature_payload = {**seal.model_dump(mode="python"), "signatureBase64": changed_signature}
    signature_payload["sealHash"] = hash_payload(
        {name: value for name, value in signature_payload.items() if name != "sealHash"}
    )
    with pytest.raises(PhaseThreeError):
        verify_ledger_seal(type(seal).model_validate(signature_payload))
    connection = duckdb.connect(str(path))
    connection.execute("UPDATE ledger_seals SET seal_hash = ?", ("0" * 64,))
    connection.close()
    with pytest.raises(PhaseThreeError) as raised:
        ledger._append_seal(seal)
    assert raised.value.reason_code is ReasonCode.LEDGER_IDENTITY_CONFLICT


def test_failed_append_receipt_is_strict_and_reason_coded() -> None:
    error = PhaseThreeError(ReasonCode.LEDGER_PATH_INVALID, "blocked", exit_code=1)
    receipt = failed_append_receipt("123e4567-e89b-12d3-a456-426614174000", None, error)
    assert receipt.validationStatus is ValidationStatus.FAIL
    assert receipt.reasonCodes == (
        ReasonCode.LEDGER_PATH_INVALID,
        ReasonCode.LEDGER_APPEND_FAILED,
    )
    with pytest.raises(ValidationError):
        type(receipt).model_validate({**receipt.model_dump(mode="python"), "extra": True})
    with pytest.raises(ValidationError):
        type(receipt).model_validate(
            {
                **receipt.model_dump(mode="python"),
                "transactionCommitted": True,
                "checkpointCompleted": True,
            }
        )


def test_lease_model_rejects_noncanonical_base64() -> None:
    receipt_id = "123e4567-e89b-12d3-a456-426614174000"
    payload = {
        "schemaId": "urn:scaffoldctl:schema:signed-asset-lease:0.3.0",
        "schemaVersion": "0.3.0",
        "leaseId": receipt_id,
        "validationReceiptId": receipt_id,
        "validationReceiptHash": "0" * 64,
        "purpose": LeasePurpose.PRE_COMMIT,
        "sourceKind": GitSnapshotSource.INDEX,
        "sourceRef": "INDEX",
        "contentMatrixSha256": "0" * 64,
        "boundarySetSha256": "0" * 64,
        "issuedAtUtc": "2026-08-03T00:00:00.000000Z",
        "expiresAtUtc": "2026-08-03T00:01:00.000000Z",
        "signerProvenance": SignerProvenance.LOCAL_REPOSITORY_KEY,
        "keyId": "0" * 64,
        "publicKeyBase64": base64.b64encode(b"x" * 32).decode(),
        "signatureBase64": base64.b64encode(b"y" * 64).decode(),
        "leaseHash": "0" * 64,
    }
    AssetLease.model_validate(payload)
    with pytest.raises(ValidationError):
        AssetLease.model_validate({**payload, "publicKeyBase64": "eA==="})
    with pytest.raises(ValidationError):
        AssetLease.model_validate({**payload, "issuedAtUtc": "2026-08-03"})


def test_ledger_payloads_are_canonical_json(tmp_path: Path) -> None:
    receipt, key, _, _ = _validation_and_key(tmp_path)
    ledger_path = tmp_path / "canonical.duckdb"
    DuckDbLedger(ledger_path).append_validation(receipt, _lease(receipt, key))  # type: ignore[arg-type]
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        payloads = connection.execute(
            "SELECT CAST(payload_json AS VARCHAR) FROM evidence_records ORDER BY monotonic_sequence"
        ).fetchall()
    finally:
        connection.close()
    for (payload,) in payloads:
        parsed = json.loads(payload)
        assert (
            json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True) == payload
        )
