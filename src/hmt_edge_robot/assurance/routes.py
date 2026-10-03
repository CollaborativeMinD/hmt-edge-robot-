"""Private software assurance API: strict native JSON and admitted catalog mutations."""

from __future__ import annotations

import base64
from typing import Callable, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
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


def routes(app: FastAPI, cell, authenticated: Callable):
    guards = [Depends(authenticated)]

    @app.get("/assurance/notices", dependencies=guards)
    def notices(after_seq: int = 0, limit: int = 32):
        return cell.assurance.kernel.notices(after_seq, limit)

    @app.get("/assurance/analytics", dependencies=guards)
    def analytics():
        return cell.assurance.analytics.summary()

    @app.post(
        "/assurance/readiness", dependencies=guards, openapi_extra=body_schema(ReadinessRequest)
    )
    async def readiness(request: Request):
        body = await native_body(request, ReadinessRequest)
        with cell.lock:
            require(cell, body)
            return cell.assurance.mcc.assess(
                body.spec, body.trace.model_copy(update={"origin": "DECLARED_TRACE"})
            )

    @app.post(
        "/assurance/attest", dependencies=guards, openapi_extra=body_schema(AttestationRequest)
    )
    async def attest(request: Request):
        body = await native_body(request, AttestationRequest)
        with cell.lock:
            require(cell, body)
            return cell.assurance.usea.attest(
                body.contract, body.trace.model_copy(update={"origin": "DECLARED_TRACE"})
            )

    @app.post("/assurance/ack", dependencies=guards, openapi_extra=body_schema(AcknowledgeRequest))
    async def acknowledge(request: Request):
        body = await native_body(request, AcknowledgeRequest)
        with cell.lock:
            require(cell, body)
            return {
                "event_hash": cell.assurance.kernel.acknowledge(body.report_hash, body.operator_id)
            }

    catalog_routes(app, cell, guards)
    mutation_routes(app, cell, guards)


def catalog_routes(app: FastAPI, cell, guards):
    @app.post(
        "/assurance/artifacts", dependencies=guards, openapi_extra=body_schema(ArtifactRequest)
    )
    async def register(request: Request):
        body = await native_body(request, ArtifactRequest)
        with cell.lock:
            require(cell, body, "reset")
            return cell.assurance.catalog.put(
                body.artifact_id, base64.b64decode(body.content_base64, validate=True)
            )

    @app.post(
        "/assurance/references", dependencies=guards, openapi_extra=body_schema(ReferenceRequest)
    )
    async def reference(request: Request):
        body = await native_body(request, ReferenceRequest)
        with cell.lock:
            require(cell, body, "reset")
            cell.assurance.catalog.update(body.record)
            return {"updated": True}

    @app.post("/assurance/plan", dependencies=guards, openapi_extra=body_schema(ObserverRequest))
    async def plan(request: Request):
        body = await native_body(request, ObserverRequest)
        with cell.lock:
            require(cell, body)
            return cell.assurance.agc.plan(cell.assurance.catalog.census())

    @app.post(
        "/assurance/bind-witness",
        dependencies=guards,
        openapi_extra=body_schema(WitnessBindingRequest),
    )
    async def bind(request: Request):
        body = await native_body(request, WitnessBindingRequest)
        return {
            "bound_artifacts": cell.assurance.bind_witness(
                body.sealed, body.session_id, body.operator_id
            )
        }


def mutation_routes(app: FastAPI, cell, guards):
    @app.post("/assurance/grant", dependencies=guards, openapi_extra=body_schema(GrantRequest))
    async def grant(request: Request):
        body = await native_body(request, GrantRequest)
        return cell.assurance.issue_grant(
            body.plan, body.action, body.artifact_id, body.session_id, body.operator_id
        )

    @app.post("/assurance/execute", dependencies=guards, openapi_extra=body_schema(ExecuteRequest))
    async def execute(request: Request):
        body = await native_body(request, ExecuteRequest)
        return cell.assurance.mutate(body.plan, body.grant)
