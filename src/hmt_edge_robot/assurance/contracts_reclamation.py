"""contracts: reclamation interface."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..contracts import Contract, Identifier, Nonnegative
from .contracts_base import Hash, MutationAction
from .contracts_identity import ArtifactRecord, Epochs
from .contracts_reports import AssuranceReport


class Census(Contract):
    epochs: Epochs
    revision: int = Field(ge=0)
    observed_at: Nonnegative
    expires_at: Nonnegative
    complete: bool
    records: Annotated[tuple[ArtifactRecord, ...], Field(max_length=1024)]

    @model_validator(mode="after")
    def census_law(self) -> Census:
        ids = [r.identity.artifact_id for r in self.records]
        if len(set(ids)) != len(ids) or self.expires_at <= self.observed_at:
            raise ValueError("CENSUS_INVALID")
        return self

class ReclamationPlan(Contract):
    census_hash: Hash
    revision: int = Field(ge=0)
    epochs: Epochs
    expires_at: Nonnegative
    decisions: Annotated[tuple[AssuranceReport, ...], Field(max_length=1024)]
    dry_run: Literal[True] = True

class MutationGrant(Contract):
    grant_id: Identifier
    operator_id: Identifier
    session_id: Identifier
    plan_hash: Hash
    epochs: Epochs
    revision: int = Field(ge=0)
    action: MutationAction
    artifact_id: Identifier
    expires_at: Nonnegative
