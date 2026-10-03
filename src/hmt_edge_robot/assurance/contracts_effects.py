"""contracts: effects interface."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..contracts import Contract, Identifier, Nonnegative, Positive
from .contracts_base import EffectKind, Hash, Refs, Text
from .contracts_identity import Epochs


class Effect(Contract):
    kind: EffectKind
    target: Text

class EffectContract(Contract):
    executable_id: Identifier
    executable_hash: Hash
    allowed: Annotated[tuple[Effect, ...], Field(max_length=256)] = ()
    required_coverage: Annotated[tuple[EffectKind, ...], Field(min_length=1, max_length=6)]
    max_runtime_sec: Positive
    allowed_exit_codes: Annotated[tuple[int, ...], Field(min_length=1, max_length=16)] = (0,)
    witness_ttl_sec: Positive = Field(default=60.0, le=3600)

    @model_validator(mode="after")
    def unique_coverage(self) -> EffectContract:
        if len(set(self.required_coverage)) != len(self.required_coverage):
            raise ValueError("DUPLICATE_COVERAGE")
        return self

class EffectTrace(Contract):
    origin: Literal["DECLARED_TRACE", "SOFTWARE_COLLECTED"] = "DECLARED_TRACE"
    collector_id: Identifier
    executable_hash: Hash
    epochs: Epochs
    started_at: Nonnegative
    runtime_sec: Nonnegative
    exit_code: int
    coverage: Annotated[tuple[EffectKind, ...], Field(max_length=6)]
    complete: bool
    observed: Annotated[tuple[Effect, ...], Field(max_length=1024)] = ()
    artifact_refs: Refs = ()
