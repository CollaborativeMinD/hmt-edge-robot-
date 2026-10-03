"""routes: catalog interface."""

from __future__ import annotations

import base64

from fastapi import FastAPI, Request

from .routes_requests import (
    ArtifactRequest,
    ExecuteRequest,
    GrantRequest,
    ObserverRequest,
    ReferenceRequest,
    WitnessBindingRequest,
    body_schema,
    native_body,
    require,
)


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
