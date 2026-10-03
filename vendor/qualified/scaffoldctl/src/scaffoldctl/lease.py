from __future__ import annotations

import base64
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.integrity import canonical_json_bytes, deterministic_id, hash_payload, sha256_bytes
from scaffoldctl.phase3_models import (
    AssetLease,
    LeasePurpose,
    PerimeterValidationReceipt,
    SignerProvenance,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus

_PRIVATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _check_path(path: str | Path) -> Path:
    absolute = Path(os.path.abspath(path))
    for candidate in (*reversed(absolute.parents), absolute):
        try:
            if candidate.is_symlink():
                raise PhaseThreeError(
                    ReasonCode.LEASE_KEY_INVALID,
                    "signing key path crosses a symlink",
                    exit_code=1,
                )
        except OSError as exc:
            raise PhaseThreeError(
                ReasonCode.LEASE_KEY_INVALID,
                "signing key path cannot be inspected",
                exit_code=1,
            ) from exc
    return absolute


def _public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def key_id(key: Ed25519PrivateKey) -> str:
    return sha256_bytes(_public_bytes(key))


def load_private_key(path: str | Path) -> Ed25519PrivateKey:
    absolute = _check_path(path)
    try:
        observed = absolute.lstat()
        if not stat.S_ISREG(observed.st_mode) or observed.st_size > 4096:
            raise ValueError("private key is not a bounded regular file")
        data = absolute.read_bytes()
        key = serialization.load_pem_private_key(data, password=None)
    except (OSError, TypeError, ValueError) as exc:
        reason = (
            ReasonCode.LEASE_KEY_MISSING if not absolute.exists() else ReasonCode.LEASE_KEY_INVALID
        )
        raise PhaseThreeError(reason, "Ed25519 private key cannot be loaded", exit_code=1) from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "signing key is not Ed25519",
            exit_code=1,
        )
    return key


def _exclusive_write(path: Path, data: bytes, mode: int) -> tuple[int, int]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, _PRIVATE_FLAGS, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        observed = os.fstat(descriptor)
        return observed.st_dev, observed.st_ino
    finally:
        os.close(descriptor)


def _public_pem(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _load_matching_public_key(path: Path, expected: bytes) -> None:
    try:
        loaded = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "public signing key is invalid",
            exit_code=1,
        ) from exc
    if not isinstance(loaded, Ed25519PublicKey) or loaded.public_bytes_raw() != expected:
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "public and private signing keys disagree",
            exit_code=1,
        )


def _preserve_keypair(private: Path, public: Path) -> tuple[str, bool]:
    key = load_private_key(private)
    public_raw = _public_bytes(key)
    if public.exists():
        _load_matching_public_key(public, public_raw)
    else:
        _exclusive_write(public, _public_pem(key), 0o644)
    return sha256_bytes(public_raw), False


def _remove_owned_private_key(path: Path, identity: tuple[int, int]) -> None:
    try:
        observed = path.lstat()
        if (observed.st_dev, observed.st_ino) == identity:
            path.unlink()
    except OSError:
        pass


def _create_keypair(private: Path, public: Path) -> tuple[str, bool]:
    key = Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    identity = _exclusive_write(private, private_pem, 0o600)
    try:
        _exclusive_write(public, _public_pem(key), 0o644)
    except Exception:
        _remove_owned_private_key(private, identity)
        raise
    return key_id(key), True


def generate_keypair(
    private_path: str | Path,
    public_path: str | Path,
) -> tuple[str, bool]:
    private = _check_path(private_path)
    public = _check_path(public_path)
    if private == public:
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "private and public key paths must differ",
            exit_code=1,
        )
    if private.exists():
        return _preserve_keypair(private, public)
    if public.exists():
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "orphaned public key blocks key generation",
            exit_code=1,
        )
    return _create_keypair(private, public)


def _lease_unsigned_payload(
    receipt: PerimeterValidationReceipt,
    purpose: LeasePurpose,
    issued_at: datetime,
    expires_at: datetime,
    provenance: SignerProvenance,
    public_key: bytes,
) -> dict[str, object]:
    if (
        receipt.validationStatus is not ValidationStatus.PASS
        or receipt.contentMatrixSha256 is None
        or receipt.boundarySetSha256 is None
    ):
        raise PhaseThreeError(
            ReasonCode.PERIMETER_INVALID,
            "a rejected perimeter cannot receive an asset lease",
            exit_code=1,
        )
    return {
        "boundarySetSha256": receipt.boundarySetSha256,
        "contentMatrixSha256": receipt.contentMatrixSha256,
        "expiresAtUtc": _timestamp(expires_at),
        "issuedAtUtc": _timestamp(issued_at),
        "keyId": sha256_bytes(public_key),
        "publicKeyBase64": base64.b64encode(public_key).decode("ascii"),
        "purpose": purpose,
        "schemaId": "urn:scaffoldctl:schema:signed-asset-lease:0.3.0",
        "schemaVersion": "0.3.0",
        "signerProvenance": provenance,
        "sourceKind": receipt.sourceKind,
        "sourceRef": receipt.sourceRef,
        "validationReceiptHash": receipt.receiptHash,
        "validationReceiptId": receipt.receiptId,
    }


def sign_asset_lease(
    receipt: PerimeterValidationReceipt,
    key: Ed25519PrivateKey,
    purpose: LeasePurpose,
    provenance: SignerProvenance,
    *,
    ttl_seconds: int = 300,
    now: datetime | None = None,
) -> AssetLease:
    if (
        not isinstance(ttl_seconds, int)
        or isinstance(ttl_seconds, bool)
        or not 1 <= ttl_seconds <= 900
    ):
        raise PhaseThreeError(
            ReasonCode.LEASE_KEY_INVALID,
            "lease lifetime must be an integer in 1..900 seconds",
            exit_code=1,
        )
    issued_at = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    public_key = _public_bytes(key)
    unsigned = _lease_unsigned_payload(
        receipt,
        purpose,
        issued_at,
        expires_at,
        provenance,
        public_key,
    )
    lease_id = deterministic_id("signed-asset-lease", hash_payload(unsigned))
    signed_payload = {**unsigned, "leaseId": lease_id}
    signature = key.sign(canonical_json_bytes(signed_payload))
    signature_b64 = base64.b64encode(signature).decode("ascii")
    payload = {**signed_payload, "signatureBase64": signature_b64}
    return AssetLease(**payload, leaseHash=hash_payload(payload))


def verify_asset_lease(
    lease: AssetLease,
    *,
    now: datetime | None = None,
    enforce_not_expired: bool = False,
) -> None:
    payload = lease.model_dump(mode="python")
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"leaseId", "signatureBase64", "leaseHash"}
    }
    expected_id = deterministic_id("signed-asset-lease", hash_payload(unsigned))
    signed_payload = {**unsigned, "leaseId": lease.leaseId}
    signature_payload = {**signed_payload, "signatureBase64": lease.signatureBase64}
    if lease.leaseId != expected_id or lease.leaseHash != hash_payload(signature_payload):
        raise PhaseThreeError(
            ReasonCode.LEASE_SIGNATURE_INVALID,
            "asset lease identity or hash is invalid",
            exit_code=1,
        )
    public_bytes = base64.b64decode(lease.publicKeyBase64, validate=True)
    if lease.keyId != sha256_bytes(public_bytes):
        raise PhaseThreeError(
            ReasonCode.LEASE_SIGNATURE_INVALID,
            "asset lease key identity is invalid",
            exit_code=1,
        )
    try:
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            base64.b64decode(lease.signatureBase64, validate=True),
            canonical_json_bytes(signed_payload),
        )
    except (InvalidSignature, ValueError) as exc:
        raise PhaseThreeError(
            ReasonCode.LEASE_SIGNATURE_INVALID,
            "asset lease signature is invalid",
            exit_code=1,
        ) from exc
    if enforce_not_expired:
        observed = now.astimezone(UTC) if now is not None else datetime.now(UTC)
        expires = datetime.fromisoformat(lease.expiresAtUtc.removesuffix("Z") + "+00:00")
        if observed >= expires:
            raise PhaseThreeError(
                ReasonCode.LEASE_EXPIRED,
                "asset lease has expired",
                exit_code=1,
            )
