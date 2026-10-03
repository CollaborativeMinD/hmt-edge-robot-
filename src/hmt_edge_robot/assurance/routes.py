"""Compatibility facade for the decomposed routes interfaces."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI, Request

from .routes_catalog import catalog_routes as catalog_routes
from .routes_catalog import mutation_routes as mutation_routes
from .routes_requests import AcknowledgeRequest as AcknowledgeRequest
from .routes_requests import ArtifactRequest as ArtifactRequest
from .routes_requests import AttestationRequest as AttestationRequest
from .routes_requests import ExecuteRequest as ExecuteRequest
from .routes_requests import GrantRequest as GrantRequest
from .routes_requests import ObserverRequest as ObserverRequest
from .routes_requests import ReadinessRequest as ReadinessRequest
from .routes_requests import ReferenceRequest as ReferenceRequest
from .routes_requests import WitnessBindingRequest as WitnessBindingRequest
from .routes_requests import body_schema as body_schema
from .routes_requests import native_body as native_body
from .routes_requests import require as require


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
