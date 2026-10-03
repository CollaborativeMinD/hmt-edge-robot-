"""Shared contracts primitives and declarations."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from ..contracts import Identifier

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

Refs = Annotated[tuple[Identifier, ...], Field(max_length=256)]

Text = Annotated[str, Field(min_length=1, max_length=512)]

MutationAction = Literal["quarantine", "restore", "delete"]

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
