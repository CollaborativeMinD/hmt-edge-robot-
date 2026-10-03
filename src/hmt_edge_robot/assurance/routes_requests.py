"""routes: requests interface."""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request
from pydantic import Field, ValidationError

from ..contracts import Contract, Identifier
from .contracts import (
    ArtifactRecord,
    EffectContract,
    EffectTrace,
    MutationGrant,
    ReclamationPlan,
    RecoverySpec,
    RecoveryTrace,
    SealedReport,
)


class ObserverRequest(Contract):
    session_id: Identifier
    operator_id: Identifier

class AcknowledgeRequest(ObserverRequest):
    report_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

class ReadinessRequest(ObserverRequest):
    spec: RecoverySpec
    trace: RecoveryTrace

class AttestationRequest(ObserverRequest):
    contract: EffectContract
    trace: EffectTrace

class ArtifactRequest(ObserverRequest):
    artifact_id: Identifier
    content_base64: str = Field(max_length=10000)

class ReferenceRequest(ObserverRequest):
    record: ArtifactRecord

class GrantRequest(ObserverRequest):
    plan: ReclamationPlan
    action: Literal["quarantine", "restore", "delete"]
    artifact_id: Identifier

class ExecuteRequest(Contract):
    plan: ReclamationPlan
    grant: MutationGrant

class WitnessBindingRequest(ObserverRequest):
    sealed: SealedReport

async def native_body(request: Request, model):
    try:
        return model.model_validate_json(await request.body())
    except ValidationError as exc:
        raise HTTPException(422, "ASSURANCE_CONTRACT_INVALID") from exc

def body_schema(model):
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": model.model_json_schema()}},
        }
    }

def require(cell, body, permission="inspect"):
    if not cell.access.authorize(body.session_id, body.operator_id, permission, cell.clock()):
        raise PermissionError("ASSURANCE_AUTHORITY_NOT_ADMITTED")
