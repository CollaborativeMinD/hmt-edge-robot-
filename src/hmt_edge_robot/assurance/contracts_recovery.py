"""contracts: recovery interface."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..contracts import Contract, Identifier, Nonnegative, Positive
from .contracts_base import Hash, Refs
from .contracts_identity import Epochs


class RecoverySpec(Contract):
    capability_id: Identifier
    capability_hash: Hash
    transaction_hash: Hash
    scenario: Literal["cold", "warm", "missing_model", "policy_refresh", "restored_state"] = "cold"
    stages: Annotated[tuple[Identifier, ...], Field(min_length=2, max_length=16)] = (
        "image_available",
        "container_started",
        "policy_loaded",
        "model_loaded",
        "admission_ready",
        "first_valid_transaction",
    )
    recovery_horizon_sec: Positive = Field(le=86400)
    reserve_sec: Nonnegative = Field(default=0.0, le=86400)
    witness_ttl_sec: Positive = Field(default=60.0, le=3600)
    artifact_refs: Refs = ()

    @model_validator(mode="after")
    def readiness_law(self) -> RecoverySpec:
        if (
            len(set(self.stages)) != len(self.stages)
            or self.stages[-1] != "first_valid_transaction"
        ):
            raise ValueError("MISSION_TRANSACTION_REQUIRED_LAST")
        return self

class StageObservation(Contract):
    stage: Identifier
    elapsed_sec: Nonnegative
    succeeded: bool
    transaction_hash: Hash | None = None

class RecoveryTrace(Contract):
    origin: Literal["DECLARED_TRACE", "SOFTWARE_COLLECTED"] = "DECLARED_TRACE"
    collector_id: Identifier
    epochs: Epochs
    started_at: Nonnegative
    observations: Annotated[tuple[StageObservation, ...], Field(max_length=16)]

class WarmCandidate(Contract):
    artifact_id: Identifier
    cost_units: int = Field(ge=1, le=1024)
    saved_sec: Nonnegative = Field(le=86400)
