"""REQ-UI-01, NF-SEC-01: authenticated private API; simulation mode explicit."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from .contracts import Contract, Identifier, MotionRequest, TaskReceipt
from .ingress import BoundedIngress
from .ledger import EvidenceError
from .runtime import RobotCell


class Login(Contract):
    operator_id: Identifier
    proof: str = Field(min_length=1, max_length=256)


class SessionRequest(Contract):
    session_id: Identifier
    operator_id: Identifier


class Question(SessionRequest):
    question: str = Field(min_length=1, max_length=2048)


def create_app(cell: RobotCell, api_token: str) -> FastAPI:
    if len(api_token) < 16:
        raise ValueError("API_TOKEN_TOO_SHORT")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        cell.close()

    app = FastAPI(title="HMT Edge Robot (SIL)", lifespan=lifespan)
    app.add_middleware(BoundedIngress)

    def authenticated(authorization: Annotated[str | None, Header()] = None) -> None:
        if authorization is None or not secrets.compare_digest(
            authorization, "Bearer " + api_token
        ):
            raise HTTPException(401, "AUTHENTICATION_REQUIRED")

    error_routes(app, cell)
    read_routes(app, cell, authenticated)
    session_routes(app, cell, authenticated)
    task_routes(app, cell, authenticated)
    resident_routes(app, cell, authenticated)
    return app


def error_routes(app: FastAPI, cell: RobotCell) -> None:
    @app.exception_handler(EvidenceError)
    async def evidence_failed(request: Any, exc: EvidenceError):
        cell.orchestrator.stop()
        return JSONResponse(status_code=503, content={"detail": "EVIDENCE_UNAVAILABLE"})

    @app.exception_handler(PermissionError)
    async def permission_failed(request: Any, exc: PermissionError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid_request(request: Any, exc: ValueError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})


def read_routes(app: FastAPI, cell: RobotCell, authenticated: Callable) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive", "mode": "SIL"}

    @app.get("/status", dependencies=[Depends(authenticated)])
    def status() -> dict[str, Any]:
        return cell.status()

    @app.get("/analytics", dependencies=[Depends(authenticated)])
    def analytics() -> dict[str, Any]:
        return {
            "event_summary": cell.analytics.summary(),
            "sensor_trends": cell.analytics.sensor_trends(),
        }

    @app.post("/simulation/observe", dependencies=[Depends(authenticated)])
    def observe() -> dict[str, Any]:
        cell.observe_simulation(cell.edge.last_seq + 1)
        return cell.status()

    @app.post("/stop", dependencies=[Depends(authenticated)])
    def stop() -> dict[str, Any]:
        cell.orchestrator.stop()
        return {"stopped": True}

    @app.post("/reset", dependencies=[Depends(authenticated)])
    def reset(body: SessionRequest) -> dict[str, bool]:
        return {"accepted": cell.orchestrator.reset(body.session_id, body.operator_id)}


def session_routes(app: FastAPI, cell: RobotCell, authenticated: Callable) -> None:
    @app.post("/sessions", dependencies=[Depends(authenticated)])
    def login(body: Login) -> dict[str, str]:
        with cell.lock:
            return {"session_id": cell.access.login(body.operator_id, body.proof, cell.clock())}

    @app.post("/sessions/heartbeat", dependencies=[Depends(authenticated)])
    def heartbeat(body: SessionRequest) -> dict[str, bool]:
        with cell.lock:
            return {
                "accepted": cell.access.heartbeat(body.session_id, body.operator_id, cell.clock())
            }

    @app.post("/sessions/revoke", dependencies=[Depends(authenticated)])
    def revoke(body: SessionRequest) -> dict[str, bool]:
        with cell.lock:
            if not cell.access.authorize(
                body.session_id, body.operator_id, "inspect", cell.clock()
            ):
                raise PermissionError("AUTHORITY_NOT_ADMITTED")
            cell.access.revoke(body.session_id)
            return {"accepted": True}


def task_routes(app: FastAPI, cell: RobotCell, authenticated: Callable) -> None:
    schema = {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": MotionRequest.model_json_schema()}},
        }
    }

    @app.post(
        "/tasks",
        dependencies=[Depends(authenticated)],
        response_model=TaskReceipt,
        openapi_extra=schema,
    )
    async def submit(body: Request) -> TaskReceipt:
        raw = bytearray()
        async for chunk in body.stream():
            raw.extend(chunk)
            if len(raw) > 16384:
                raise HTTPException(413, "REQUEST_TOO_LARGE")
        try:
            order = MotionRequest.model_validate_json(bytes(raw))
        except ValidationError as exc:
            raise HTTPException(422, "MOTION_CONTRACT_INVALID") from exc
        return cell.orchestrator.submit(order)

    @app.post("/tasks/{request_id}/cancel", dependencies=[Depends(authenticated)])
    def cancel(request_id: str, body: SessionRequest) -> TaskReceipt:
        return cell.orchestrator.cancel(request_id, body.session_id, body.operator_id)

    @app.post("/cycle", dependencies=[Depends(authenticated)])
    def cycle() -> TaskReceipt | None:
        return cell.orchestrator.run_next()


def resident_routes(app: FastAPI, cell: RobotCell, authenticated: Callable) -> None:
    @app.post("/resident", dependencies=[Depends(authenticated)])
    async def resident(body: Question) -> dict[str, Any]:
        with cell.lock:
            if not cell.access.authorize(
                body.session_id, body.operator_id, "inspect", cell.clock()
            ):
                raise PermissionError("AUTHORITY_NOT_ADMITTED")
            state = cell.status()
        receipt = await cell.resident.ask(state, body.question)
        result = (
            cell.resident_tool(receipt.proposal.action, body.session_id, body.operator_id)
            if receipt.proposal
            else None
        )
        return {"receipt": receipt.model_dump(mode="json"), "tool_result": result}
