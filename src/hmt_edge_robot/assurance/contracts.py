"""Strict software assurance contracts; identity, observation and decisions are separate."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..contracts import Contract, Identifier, Nonnegative, Positive

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Refs = Annotated[tuple[Identifier, ...], Field(max_length=256)]
Text = Annotated[str, Field(min_length=1, max_length=512)]
EffectKind = Literal["read", "write", "network", "secret", "spawn", "mount"]
Verdict = Literal[
    "MISSION_READY",
    "RECOVERY_PATH_NOT_AFFORDABLE",
    "FIRST_TRANSACTION_FAILED",
    "IMAGE_UNAVAILABLE",
    "POLICY_LOAD_FAILED",
    "MODEL_LOAD_EXCEEDS_HORIZON",
    "K8S_READY_BUT_MISSION_NOT_READY",
    "ATTESTATION_INCOMPLETE",
    "DECLARED_EFFECT_CONFIRMED",
    "SIDE_EFFECT_OUTSIDE_CONTRACT",
    "LIVE",
    "RECOVERY_REQUIRED",
    "EVIDENCE_REQUIRED",
    "UNKNOWN_HOLD",
    "SAFE_TO_RECLAIM",
    "QUARANTINE",
    "RECLAIMED",
    "RESTORED",
]


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


class AssuranceReport(Contract):
    component: Literal["MCC", "USEA", "AGC"]
    scope: WitnessScope
    verdict: Verdict
    reason_codes: Refs
    artifact_refs: Refs = ()
    observation_hash: Hash
    metrics: Annotated[tuple[tuple[Identifier, Nonnegative], ...], Field(max_length=32)] = ()
    dry_run: bool = True


class SealedReport(Contract):
    report: AssuranceReport
    report_hash: Hash
    event_hash: Hash


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
    action: Literal["quarantine", "restore", "delete"]
    artifact_id: Identifier
    expires_at: Nonnegative


class WarmCandidate(Contract):
    artifact_id: Identifier
    cost_units: int = Field(ge=1, le=1024)
    saved_sec: Nonnegative = Field(le=86400)
