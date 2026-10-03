from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from phase3_support import init_repository
from pydantic import ValidationError

from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import GitRepository, _make_matrix
from scaffoldctl.hook import install_hook
from scaffoldctl.integrity import hash_payload
from scaffoldctl.lease import load_private_key, sign_asset_lease
from scaffoldctl.ledger import DuckDbLedger
from scaffoldctl.perimeter import validate_index_snapshot
from scaffoldctl.phase3_models import (
    AssetLease,
    BoundaryValidationRecord,
    GitObjectEntry,
    GitObjectFormat,
    GitObjectMatrix,
    GitSnapshotSource,
    HookExecutionReceipt,
    LeasePurpose,
    LedgerAppendReceipt,
    LedgerSeal,
    LedgerVerificationReceipt,
    PerimeterValidationReceipt,
    SignerProvenance,
    _validate_b64,
    _validate_timestamp,
    canonical_git_path,
)
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus


def _phase_three_models(
    tmp_path: Path,
) -> tuple[
    PerimeterValidationReceipt,
    AssetLease,
    LedgerAppendReceipt,
    LedgerVerificationReceipt,
    LedgerSeal,
    HookExecutionReceipt,
]:
    root = tmp_path / "repo"
    init_repository(root)
    install_hook(str(root))
    validation = validate_index_snapshot(GitRepository(root))
    key = load_private_key(root / ".git/scaffoldctl/lease-signing-key.pem")
    lease = sign_asset_lease(
        validation,
        key,
        LeasePurpose.PRE_COMMIT,
        SignerProvenance.LOCAL_REPOSITORY_KEY,
        now=datetime(2026, 8, 3, tzinfo=UTC),
    )
    ledger = DuckDbLedger(tmp_path / "ledger.duckdb")
    append = ledger.append_validation(validation, lease)
    verification = ledger.verify()
    seal = ledger.seal(key, SignerProvenance.RELEASE_KEY, now=datetime(2026, 8, 3, tzinfo=UTC))
    hook_payload = {
        "assetLease": lease,
        "exitCode": 0,
        "ledgerAppendReceipt": append,
        "reasonCodes": (ReasonCode.HOOK_ADMITTED,),
        "schemaId": "urn:scaffoldctl:schema:hook-execution-receipt:0.3.0",
        "schemaVersion": "0.3.0",
        "validationReceipt": validation,
        "validationStatus": ValidationStatus.PASS,
    }
    hook = HookExecutionReceipt(**hook_payload, receiptHash=hash_payload(hook_payload))
    return validation, lease, append, verification, seal, hook


@pytest.mark.parametrize(
    "value",
    ("", "/absolute", "back\\slash", "a\x00b", "a/../b", "e\u0301.txt"),
)
def test_canonical_git_paths_reject_ambiguous_values(value: str) -> None:
    with pytest.raises(ValueError):
        canonical_git_path(value)
    assert canonical_git_path("docs/é.txt") == "docs/é.txt"


def test_scalar_validators_reject_noncanonical_values() -> None:
    with pytest.raises(ValueError):
        _validate_timestamp("2026-08-03T00:00:00+02:00")
    with pytest.raises(ValueError):
        _validate_b64("%%%=")
    with pytest.raises(ValueError):
        _validate_b64("AB==")


def test_git_object_entry_mode_type_and_size_are_consistent() -> None:
    base = {
        "relativePath": "module",
        "objectMode": "160000",
        "objectType": "commit",
        "objectId": "a" * 40,
        "objectSize": None,
        "stage": 0,
    }
    GitObjectEntry.model_validate(base)
    with pytest.raises(ValidationError):
        GitObjectEntry.model_validate({**base, "objectType": "blob"})
    with pytest.raises(ValidationError):
        GitObjectEntry.model_validate({**base, "objectSize": 1})


def test_git_matrix_rejects_count_order_parent_and_source_drift() -> None:
    first = GitObjectEntry(
        relativePath="a",
        objectMode="100644",
        objectType="blob",
        objectId="a" * 40,
        objectSize=1,
        stage=0,
    )
    child = GitObjectEntry(
        relativePath="a/b",
        objectMode="100644",
        objectType="blob",
        objectId="b" * 40,
        objectSize=1,
        stage=0,
    )
    good = _make_matrix(GitSnapshotSource.INDEX, "INDEX", GitObjectFormat.SHA1, (first,))
    with pytest.raises(ValidationError):
        GitObjectMatrix.model_validate({**good.model_dump(mode="python"), "entryCount": 2})
    unsorted = (child, first)
    content = hash_payload(tuple(item.model_dump(mode="json") for item in unsorted))
    matrix_hash = hash_payload(
        {
            "contentMatrixSha256": content,
            "objectFormat": GitObjectFormat.SHA1,
            "sourceKind": GitSnapshotSource.INDEX,
            "sourceRef": "INDEX",
        }
    )
    with pytest.raises(ValidationError):
        GitObjectMatrix.model_validate(
            {
                **good.model_dump(mode="python"),
                "entryCount": 2,
                "entries": unsorted,
                "contentMatrixSha256": content,
                "matrixSha256": matrix_hash,
            }
        )
    with pytest.raises(PhaseThreeError):
        _make_matrix(
            GitSnapshotSource.INDEX,
            "INDEX",
            GitObjectFormat.SHA1,
            (first, child),
        )
    with pytest.raises(ValidationError):
        GitObjectMatrix.model_validate(
            {
                **good.model_dump(mode="python"),
                "sourceRef": "HEAD",
                "matrixSha256": hash_payload(
                    {
                        "contentMatrixSha256": good.contentMatrixSha256,
                        "objectFormat": GitObjectFormat.SHA1,
                        "sourceKind": GitSnapshotSource.INDEX,
                        "sourceRef": "HEAD",
                    }
                ),
            }
        )


def test_receipt_models_reject_inconsistent_dispositions(tmp_path: Path) -> None:
    validation, _, append, verification, _, _ = _phase_three_models(tmp_path)
    boundary = validation.boundaries[0]
    with pytest.raises(ValidationError):
        BoundaryValidationRecord.model_validate(
            {**boundary.model_dump(mode="python"), "admitted": False}
        )
    with pytest.raises(ValidationError):
        PerimeterValidationReceipt.model_validate(
            {**validation.model_dump(mode="python"), "exitCode": 1}
        )
    with pytest.raises(ValidationError):
        PerimeterValidationReceipt.model_validate(
            {
                **validation.model_dump(mode="python"),
                "reasonCodes": (
                    ReasonCode.PERIMETER_VALID,
                    ReasonCode.PERIMETER_VALID,
                ),
            }
        )
    with pytest.raises(ValidationError):
        PerimeterValidationReceipt.model_validate(
            {**validation.model_dump(mode="python"), "matrixSha256": None}
        )
    rejected = BoundaryValidationRecord.model_validate(
        {
            **boundary.model_dump(mode="python"),
            "admitted": False,
            "validationStatus": ValidationStatus.FAIL,
        }
    )
    with pytest.raises(ValidationError):
        PerimeterValidationReceipt.model_validate(
            {**validation.model_dump(mode="python"), "boundaries": (rejected,)}
        )
    with pytest.raises(ValidationError):
        LedgerAppendReceipt.model_validate(
            {
                **append.model_dump(mode="python"),
                "firstSequence": None,
                "lastSequence": None,
                "chainHeadSha256": None,
            }
        )
    with pytest.raises(ValidationError):
        LedgerVerificationReceipt.model_validate(
            {**verification.model_dump(mode="python"), "chainValid": False}
        )
    with pytest.raises(ValidationError):
        LedgerVerificationReceipt.model_validate(
            {
                **verification.model_dump(mode="python"),
                "recordCount": 0,
                "firstSequence": 0,
                "lastSequence": 0,
            }
        )
    with pytest.raises(ValidationError):
        LedgerVerificationReceipt.model_validate(
            {**verification.model_dump(mode="python"), "lastSequence": 9}
        )


def test_lease_seal_and_hook_models_reject_structural_drift(tmp_path: Path) -> None:
    validation, lease, _, _, seal, hook = _phase_three_models(tmp_path)
    with pytest.raises(ValidationError):
        AssetLease.model_validate(
            {**lease.model_dump(mode="python"), "expiresAtUtc": lease.issuedAtUtc}
        )
    with pytest.raises(ValidationError):
        AssetLease.model_validate(
            {
                **lease.model_dump(mode="python"),
                "publicKeyBase64": base64.b64encode(b"short").decode(),
            }
        )
    for changed in (
        {"lastSequence": 10},
        {"recordCount": 3, "lastSequence": 2},
        {"publicKeyBase64": base64.b64encode(b"x" * 31).decode()},
        {"signatureBase64": base64.b64encode(b"x" * 63).decode()},
    ):
        with pytest.raises(ValidationError):
            LedgerSeal.model_validate({**seal.model_dump(mode="python"), **changed})
    with pytest.raises(ValidationError):
        HookExecutionReceipt.model_validate(
            {
                **hook.model_dump(mode="python"),
                "assetLease": None,
                "validationStatus": ValidationStatus.PASS,
                "exitCode": 0,
            }
        )
    with pytest.raises(ValidationError):
        type(validation).model_validate({**validation.model_dump(mode="python"), "unknown": True})
    with pytest.raises(ValidationError):
        type(validation).model_validate(
            {**validation.model_dump(mode="python"), "sourceKind": "git_index"}
        )
