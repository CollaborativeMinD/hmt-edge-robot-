"""REQ-CD4-01/03: artifact qualification never grants deployment authority."""
from __future__ import annotations

from typing import Annotated, Literal

from deployment_contracts import Closed, GitHash, Hash
from pydantic import Field

ImageDigest = Annotated[str, Field(pattern=r"^sha256:[a-f0-9]{64}$")]


class ArtifactReceipt(Closed):
    schema_version: Literal[1]
    status: Literal["PASS"]
    stage: Literal[4]
    source_commit: GitHash
    image_digest: ImageDigest
    archive_sha256: Hash
    inputs: dict[str, Hash] = Field(min_length=6, max_length=32)
    platform: Literal["linux/arm64"]
    authority: Literal["ARTIFACT_QUALIFICATION_ONLY"]
    deployment: Literal["HOLD"]
    hardware: Literal["HOLD"]
    vulnerability_disposition: Literal["NO_HIGH_CRITICAL_OR_SECRETS;LOW_MEDIUM_RECORDED", "NO_HIGH_CRITICAL_OR_SECRETS;OWNER_ACCEPTED_UNKNOWN_RECORDED"]
    vulnerability_exceptions: list[dict] = Field(default_factory=list, max_length=1)
    notification: Literal["ARM64_ARTIFACT_QUALIFIED_DEPLOYMENT_HELD"]
    alert: Literal[False]
    receipt_hash: Hash


def require_deployment(receipt: ArtifactReceipt) -> None:
    raise PermissionError("STAGE4_DEPLOYMENT_NOT_AUTHORIZED")
