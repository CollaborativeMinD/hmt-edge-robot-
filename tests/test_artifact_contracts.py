"""Tracer: artifact PASS cannot be relabeled as a deployment grant."""
from __future__ import annotations

import pytest
from artifact_contracts import ArtifactReceipt, require_deployment
from pydantic import ValidationError


def payload() -> dict:
    return {"schema_version": 1, "status": "PASS", "stage": 4,
        "source_commit": "1" * 40, "image_digest": "sha256:" + "2" * 64,
        "archive_sha256": "3" * 64, "inputs": {str(i): "4" * 64 for i in range(6)},
        "platform": "linux/arm64", "authority": "ARTIFACT_QUALIFICATION_ONLY",
        "deployment": "HOLD", "hardware": "HOLD",
        "vulnerability_disposition": "NO_HIGH_CRITICAL_OR_SECRETS;LOW_MEDIUM_RECORDED",
        "notification": "ARM64_ARTIFACT_QUALIFIED_DEPLOYMENT_HELD", "alert": False,
        "receipt_hash": "5" * 64}


def test_artifact_pass_cannot_authorize_deployment() -> None:
    with pytest.raises(PermissionError, match="NOT_AUTHORIZED"):
        require_deployment(ArtifactReceipt.model_validate(payload()))


@pytest.mark.parametrize("key,value", [("deployment", "PASS"), ("hardware", "PASS"),
    ("platform", "linux/amd64"), ("alert", 0), ("schema_version", True),
    ("authority", "DEPLOY"), ("image_digest", "latest"), ("unknown", 1)])
def test_artifact_contract_rejects_authority_widening(key: str, value: object) -> None:
    candidate = payload()
    candidate[key] = value
    with pytest.raises(ValidationError):
        ArtifactReceipt.model_validate(candidate)
