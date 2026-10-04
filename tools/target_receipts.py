"""REQ-CD5-03: typed inventory outcomes, finite vocabulary and fixed authority."""
from __future__ import annotations

from typing import Annotated, Literal

from deployment_contracts import Closed, Hash
from pydantic import Field, TypeAdapter, field_validator, model_validator
from target_contracts import Host, Text


class InventoryReceipt(Closed):
    schema_version: Literal[1]
    inventory_status: Literal["PASS"]
    target_qualification: Literal["HOLD"]
    deployment: Literal["HOLD"]
    physical_actuation: Literal["HOLD"]
    authority: Literal["INVENTORY_CONSISTENCY_ONLY"]
    assessed_at: Text
    policy_hash: Hash
    collector_hash: Hash
    captures: dict[Host, Hash] = Field(min_length=3, max_length=3)
    reason_codes: tuple[Text, ...] = Field(min_length=11, max_length=32)
    alert: Literal[True]
    receipt_hash: Hash

    @field_validator("reason_codes", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value

    @model_validator(mode="after")
    def integrity(self) -> InventoryReceipt:
        from datetime import datetime, timedelta

        from deployment_receipts import content_hash

        if datetime.fromisoformat(self.assessed_at).utcoffset() != timedelta(0):
            raise ValueError("RECEIPT_UTC_REQUIRED")
        if content_hash(self.model_dump(mode="json", exclude={"receipt_hash"})) != self.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return self


class Rejection(Closed):
    inventory_status: Literal["FAIL"]
    target_qualification: Literal["HOLD"]
    deployment: Literal["HOLD"]
    physical_actuation: Literal["HOLD"]
    reason_codes: tuple[Literal["ASSESSMENT_INCOMPLETE", "TARGET_ASSESSMENT_REJECTED"], ...] = Field(min_length=1, max_length=1)
    alert: Literal[True]

    @field_validator("reason_codes", mode="before")
    @classmethod
    def json_array(cls, value: object) -> object:
        return tuple(value) if type(value) is list else value


Outcome = TypeAdapter(Annotated[InventoryReceipt | Rejection, Field(discriminator="inventory_status")])
