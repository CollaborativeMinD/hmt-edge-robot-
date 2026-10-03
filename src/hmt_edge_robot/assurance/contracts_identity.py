"""contracts: identity interface."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from ..contracts import Contract, Identifier, Nonnegative
from .contracts_base import Hash, Refs, Text


class Epochs(Contract):
    runtime: int = Field(default=0, ge=0)
    policy: int = Field(default=1, ge=1)
    department: int = Field(default=0, ge=0)
    membership: int = Field(default=0, ge=0)

class ArtifactIdentity(Contract):
    artifact_id: Identifier
    artifact_type: Identifier
    identity_hash: Hash
    owner_surface: Identifier
    generation: int = Field(ge=1)
    size_bytes: int = Field(ge=0, le=16_777_216)
    created_at_utc: Text

class ArtifactRecord(Contract):
    identity: ArtifactIdentity
    epochs: Epochs = Epochs()
    authority_refs: Refs = ()
    recovery_refs: Refs = ()
    evidence_refs: Refs = ()
    side_effect_refs: Refs = ()
    cold_start_refs: Refs = ()
    dependencies: Refs = ()

class WitnessScope(Contract):
    subject_id: Identifier
    subject_hash: Hash
    contract_hash: Hash
    collector_id: Identifier
    epochs: Epochs
    observed_at: Nonnegative
    expires_at: Nonnegative
    coverage: Annotated[tuple[Identifier, ...], Field(max_length=32)]

    @model_validator(mode="after")
    def time_order(self) -> WitnessScope:
        if self.expires_at <= self.observed_at or len(set(self.coverage)) != len(self.coverage):
            raise ValueError("WITNESS_SCOPE_INVALID")
        return self
