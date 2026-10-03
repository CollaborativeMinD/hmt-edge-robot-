"""Deterministic design receipts convey no image, cluster or motion admission."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from deployment_contracts import Baseline, Boundaries, Closed, Hash
from pydantic import Field
from truth_serum_runtime.gates.data_parse import loads_json


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReleaseCandidate(Closed):
    schema_version: Literal[1]
    release_name: Literal["hmt-edge-robot-sil-stage3"]
    baseline: Baseline
    plan_sha256: Hash
    source_inventory_sha256: Hash
    artifact_status: Literal["UNBUILT"]
    image_digest: None
    target_observation: None
    authorization: Literal["DESIGN_ONLY"]


class ReleaseReceipt(Closed):
    schema_version: Literal[1]
    release_id: str = Field(pattern=r"^stage3-[a-f0-9]{24}$")
    contract_status: Literal["PASS"]
    release_decision: Literal["HOLD"]
    baseline: Baseline
    candidate_sha256: Hash
    source_inventory_sha256: Hash
    artifacts: dict[str, Hash] = Field(min_length=1, max_length=32)
    boundaries: Boundaries
    reason_codes: list[str] = Field(min_length=1, max_length=16)
    image_digest: None
    authority: Literal["DESIGN_ONLY"]
    notification: Literal["DEPLOYMENT_DESIGN_VALIDATED_EXECUTION_HELD"]
    alert: Literal[False]
    receipt_hash: Hash


def verify_receipt(expected: ReleaseReceipt, raw: bytes) -> ReleaseReceipt:
    if len(raw) > 65536:
        raise ValueError("RECEIPT_TOO_LARGE")
    value = ReleaseReceipt.model_validate_json(json.dumps(loads_json(raw.decode())))
    payload = value.model_dump(mode="json", exclude={"receipt_hash"})
    if value.receipt_hash != content_hash(payload) or value != expected:
        raise ValueError("RELEASE_RECEIPT_STALE_OR_TAMPERED")
    return value


def require_execution(receipt: ReleaseReceipt) -> None:
    raise PermissionError("STAGE3_EXECUTION_NOT_AUTHORIZED")
