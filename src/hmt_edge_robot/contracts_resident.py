"""contracts: resident interface."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .contracts_base import (
    Contract,
    Finite,
    Identifier,
    ModelIdentifier,
    Nonnegative,
    Positive,
    Vector3,
)


class GraspObservation(Contract):
    target_mm: Vector3
    angle_deg: Finite
    primary_eigenvalue: Positive
    secondary_eigenvalue: Nonnegative
    ambiguity_ratio: Annotated[float, Field(ge=0, le=1)]
    calibration_id: Identifier
    frame_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

class ResidentProposal(Contract):
    action: Literal["inspect", "diagnose", "plan_grasp", "hold"]
    explanation: str = Field(min_length=1, max_length=2048)
    evidence_refs: tuple[str, ...] = Field(max_length=32)

class ResidentReceipt(Contract):
    decision: Literal["ADMIT", "HOLD", "DENY"]
    proposal: ResidentProposal | None
    model_id: ModelIdentifier
    context_hash: str
    rejection_reason: str
    evidence_id: str
