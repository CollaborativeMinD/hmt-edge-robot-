"""Hash-bound human approval overlay; historical policy bytes remain unchanged."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from ci_admission import confined, digest
from policy_contracts import SupportProfile
from pydantic import BaseModel, ConfigDict, Field

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class DisregardedSource(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    artifact: Literal["sql-quality-automation-pipeline project.zip"]
    sha256: Literal["9010f01755da035d1b0e26122063deb0ccd5529208de08a9fabed891849f100b"]
    reason: str = Field(min_length=1, max_length=1024)


class Promotion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1]
    promotion_id: Literal["HMT-POLICY-PROMOTION-01"]
    status: Literal["HUMAN_APPROVED"]
    recorded_at_utc: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
    authority: str = Field(min_length=1, max_length=1024)
    approval_text: str = Field(min_length=1, max_length=2048)
    scope: Literal["system_software_validation"]
    policy_bundle_sha256: Hash
    policy_sources: dict[str, Hash] = Field(min_length=1, max_length=128)
    module_loc_limit: Literal[100]
    function_physical_loc_limit: Literal[60]
    disregarded_source: DisregardedSource
    full_tool_admission: Literal["HOLD"]
    docker_build: Literal["HOLD"]
    deployment: Literal["HOLD"]


def load_promotion(root: Path, profile: SupportProfile) -> Promotion:
    record = Promotion.model_validate_json(confined(root, "policy/promotion.json").read_bytes())
    if record.policy_sources != profile.policy_sources:
        raise ValueError("PROMOTION_SOURCE_SET_MISMATCH")
    if digest(confined(root, "vendor/admission/hmt-policy.zip")) != record.policy_bundle_sha256:
        raise ValueError("PROMOTION_BUNDLE_DIGEST_MISMATCH")
    return record


def disposition_pins(rows: list[dict], record: Promotion) -> list[dict]:
    result = []
    for row in rows:
        historical = dict(row)
        if (row["artifact"] == record.disregarded_source.artifact
                and row["expected_sha256"] == record.disregarded_source.sha256):
            historical.update(status="DISREGARDED_BY_HUMAN", historical_status=row["status"],
                              reason=record.disregarded_source.reason)
        elif row["status"] != "PASS":
            raise ValueError("UNDISPOSITIONED_SOURCE_PIN:" + row["artifact"])
        result.append(historical)
    return result
