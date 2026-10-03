from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from contextlib import suppress
from importlib.resources import files
from pathlib import Path

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import GitObjectSnapshot, GitRepository
from scaffoldctl.integrity import hash_payload, sha256_bytes
from scaffoldctl.lease import generate_keypair, load_private_key, sign_asset_lease
from scaffoldctl.ledger import DuckDbLedger, failed_append_receipt
from scaffoldctl.perimeter import (
    failure_perimeter_receipt,
    validate_index_snapshot,
    validate_snapshot,
)
from scaffoldctl.phase3_models import (
    AssetLease,
    GitSnapshotSource,
    HookConfig,
    HookExecutionReceipt,
    HookInstallReceipt,
    KeyGenerationReceipt,
    LeasePurpose,
    PerimeterOperation,
    PerimeterValidationReceipt,
    SignerProvenance,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus

_HOOK_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _unique(values: Iterable[ReasonCode]) -> tuple[ReasonCode, ...]:
    result: list[ReasonCode] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)


def _hook_receipt(
    validation: PerimeterValidationReceipt,
    lease: AssetLease | None,
    ledger_append: object | None,
) -> HookExecutionReceipt:
    admitted = (
        validation.validationStatus is ValidationStatus.PASS
        and lease is not None
        and ledger_append is not None
        and getattr(ledger_append, "validationStatus", None) is ValidationStatus.PASS
    )
    reasons: tuple[ReasonCode, ...]
    if admitted:
        reasons = (
            ReasonCode.PERIMETER_VALID,
            ReasonCode.LEASE_SIGNED,
            ReasonCode.LEDGER_APPEND_COMMITTED,
            ReasonCode.HOOK_ADMITTED,
        )
    else:
        ledger_reasons = () if ledger_append is None else tuple(ledger_append.reasonCodes)
        reasons = _unique(
            (
                *validation.reasonCodes,
                *ledger_reasons,
                ReasonCode.HOOK_REJECTED,
            )
        )
    payload = {
        "assetLease": lease,
        "exitCode": 0 if admitted else 1,
        "ledgerAppendReceipt": ledger_append,
        "reasonCodes": reasons,
        "schemaId": "urn:scaffoldctl:schema:hook-execution-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "validationReceipt": validation,
        "validationStatus": ValidationStatus.PASS if admitted else ValidationStatus.FAIL,
    }
    return HookExecutionReceipt(**payload, receiptHash=hash_payload(payload))


def _persist(
    ledger_path: str,
    receipt: PerimeterValidationReceipt,
    lease: AssetLease | None,
) -> HookExecutionReceipt:
    try:
        append_receipt = DuckDbLedger(ledger_path).append_validation(receipt, lease)
    except Exception as exc:
        append_receipt = failed_append_receipt(
            receipt.receiptId,
            None if lease is None else lease.leaseId,
            exc,
        )
    return _hook_receipt(receipt, lease, append_receipt)


def execute_pre_commit(config: HookConfig) -> HookExecutionReceipt:
    try:
        key = load_private_key(config.privateKeyPath)
        repository = GitRepository(config.repositoryRoot)
        baseline = None
        if config.baselineTree == "HEAD":
            matrix = repository.capture_optional_head_matrix()
            baseline = None if matrix is None else GitObjectSnapshot(repository, matrix)
        elif config.baselineTree is not None:
            baseline = GitObjectSnapshot(
                repository,
                repository.capture_tree_matrix(config.baselineTree),
            )
        receipt = validate_index_snapshot(repository, baseline=baseline)
        lease = None
        if receipt.validationStatus is ValidationStatus.PASS:
            lease = sign_asset_lease(
                receipt,
                key,
                LeasePurpose.PRE_COMMIT,
                config.signerProvenance,
                ttl_seconds=config.leaseTtlSeconds,
            )
    except Exception as exc:
        receipt = failure_perimeter_receipt(
            PerimeterOperation.VALIDATE_STAGED,
            GitSnapshotSource.INDEX,
            "INDEX",
            exc,
        )
        lease = None
    return _persist(config.ledgerPath, receipt, lease)


def execute_tree_validation(
    *,
    root: str,
    treeish: str,
    baseline_treeish: str | None,
    ledger_path: str,
    private_key_path: str,
    provenance: SignerProvenance,
    lease_ttl_seconds: int = 300,
) -> HookExecutionReceipt:
    try:
        key = load_private_key(private_key_path)
        repository = GitRepository(root)
        snapshot = GitObjectSnapshot(repository, repository.capture_tree_matrix(treeish))
        baseline = (
            None
            if baseline_treeish is None
            else GitObjectSnapshot(
                repository,
                repository.capture_tree_matrix(baseline_treeish),
            )
        )
        receipt = validate_snapshot(
            snapshot,
            PerimeterOperation.VALIDATE_TREE,
            baseline=baseline,
        )
        lease = None
        if receipt.validationStatus is ValidationStatus.PASS:
            lease = sign_asset_lease(
                receipt,
                key,
                LeasePurpose.CI_ADMISSION,
                provenance,
                ttl_seconds=lease_ttl_seconds,
            )
    except Exception as exc:
        receipt = failure_perimeter_receipt(
            PerimeterOperation.VALIDATE_TREE,
            GitSnapshotSource.TREE,
            treeish,
            exc,
        )
        lease = None
    return _persist(ledger_path, receipt, lease)


def keygen_receipt(private_path: str, public_path: str) -> KeyGenerationReceipt:
    observed_key_id, created = generate_keypair(private_path, public_path)
    reason = ReasonCode.LEASE_KEY_CREATED if created else ReasonCode.LEASE_KEY_PRESERVED
    payload = {
        "created": created,
        "keyId": observed_key_id,
        "reasonCodes": (reason,),
        "schemaId": "urn:scaffoldctl:schema:key-generation-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "validationStatus": ValidationStatus.PASS,
    }
    return KeyGenerationReceipt(**payload, receiptHash=hash_payload(payload))


def _hook_resource() -> bytes:
    return files("scaffoldctl.resources").joinpath("git_perimeter", "pre-commit").read_bytes()


def _check_hook_path(path: Path) -> None:
    if path.parent.is_symlink() or path.is_symlink():
        raise PhaseThreeError(
            ReasonCode.HOOK_INSTALL_CONFLICT,
            "Git hook path crosses a symlink",
            exit_code=1,
        )
    if path.exists() and not stat.S_ISREG(path.lstat().st_mode):
        raise PhaseThreeError(
            ReasonCode.HOOK_INSTALL_CONFLICT,
            "Git hook path is not a regular file",
            exit_code=1,
        )


def _read_relative_hook(directory: int) -> bytes | None:
    try:
        descriptor = os.open(
            "pre-commit",
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory,
        )
    except FileNotFoundError:
        return None
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_size > 65536:
            raise PhaseThreeError(
                ReasonCode.HOOK_INSTALL_CONFLICT,
                "existing pre-commit hook is not a bounded regular file",
                exit_code=1,
            )
        chunks = []
        while True:
            chunk = os.read(descriptor, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _hook_directory(git_dir: Path) -> tuple[int, int]:
    git_descriptor = os.open(git_dir, _DIRECTORY_FLAGS)
    try:
        with suppress(FileExistsError):
            os.mkdir("hooks", 0o755, dir_fd=git_descriptor)
        hooks_descriptor = os.open("hooks", _DIRECTORY_FLAGS, dir_fd=git_descriptor)
    except OSError as exc:
        os.close(git_descriptor)
        raise PhaseThreeError(
            ReasonCode.HOOK_INSTALL_CONFLICT,
            "Git hook directory cannot be opened without following links",
            exit_code=1,
        ) from exc
    return git_descriptor, hooks_descriptor


def _publish_hook(hooks_descriptor: int, hook_data: bytes) -> None:
    descriptor = os.open("pre-commit", _HOOK_FLAGS, 0o755, dir_fd=hooks_descriptor)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(hook_data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _set_hook_mode(hooks_descriptor: int) -> None:
    descriptor = os.open(
        "pre-commit",
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=hooks_descriptor,
    )
    try:
        os.fchmod(descriptor, 0o755)
    finally:
        os.close(descriptor)


def _verify_hook_directory(git_descriptor: int, hooks_descriptor: int) -> None:
    current = os.stat("hooks", dir_fd=git_descriptor, follow_symlinks=False)
    opened = os.fstat(hooks_descriptor)
    if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
        raise PhaseThreeError(
            ReasonCode.HOOK_INSTALL_CONFLICT,
            "Git hook directory identity changed during installation",
            exit_code=1,
        )


def _install_hook_receipt(
    hook_created: bool,
    hook_data: bytes,
    key_receipt: KeyGenerationReceipt,
) -> HookInstallReceipt:
    reason = ReasonCode.HOOK_INSTALL_CREATED if hook_created else ReasonCode.HOOK_INSTALL_PRESERVED
    payload = {
        "hookCreated": hook_created,
        "hookSha256": sha256_bytes(hook_data),
        "keyCreated": key_receipt.created,
        "keyId": key_receipt.keyId,
        "reasonCodes": (reason, *key_receipt.reasonCodes),
        "schemaId": "urn:scaffoldctl:schema:hook-install-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "validationStatus": ValidationStatus.PASS,
    }
    return HookInstallReceipt(**payload, receiptHash=hash_payload(payload))


def install_hook(root: str) -> HookInstallReceipt:
    repository = GitRepository(root)
    hook_path = repository.git_dir / "hooks" / "pre-commit"
    key_directory = repository.git_dir / "scaffoldctl"
    private_path = key_directory / "lease-signing-key.pem"
    public_path = key_directory / "lease-signing-key.pub.pem"
    hook_data = _hook_resource()
    _check_hook_path(hook_path)
    git_descriptor, hooks_descriptor = _hook_directory(repository.git_dir)
    try:
        existing = _read_relative_hook(hooks_descriptor)
        if existing is not None and existing != hook_data:
            raise PhaseThreeError(
                ReasonCode.HOOK_INSTALL_CONFLICT,
                "existing pre-commit hook differs and will not be overwritten",
                exit_code=1,
            )
        key_receipt = keygen_receipt(os.fspath(private_path), os.fspath(public_path))
        hook_created = existing is None
        if hook_created:
            _publish_hook(hooks_descriptor, hook_data)
        _set_hook_mode(hooks_descriptor)
        _verify_hook_directory(git_descriptor, hooks_descriptor)
        os.fsync(hooks_descriptor)
    finally:
        os.close(hooks_descriptor)
        os.close(git_descriptor)
    return _install_hook_receipt(hook_created, hook_data, key_receipt)
