"""REQ-UI-01, NF-SEC-01: authenticated private API; simulation mode explicit."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException

from .contracts import Contract, Identifier, MotionRequest, TaskReceipt
from .ledger import EvidenceError
from .runtime import RobotCell


class Login(Contract):
    operator_id: Identifier
    proof: str


class SessionRequest(Contract):
    session_id: Identifier
    operator_id: Identifier


class Question(SessionRequest):
    question: str


def create_app(cell: RobotCell, api_token: str) -> FastAPI:
    if len(api_token) < 16:
        raise ValueError("API_TOKEN_TOO_SHORT")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        cell.close()

    app = FastAPI(title="HMT Edge Robot (SIL)", lifespan=lifespan)

    def authenticated(authorization: Annotated[str | None, Header()] = None) -> None:
        if authorization is None or not secrets.compare_digest(authorization, "Bearer " + api_token):
            raise HTTPException(401, "AUTHENTICATION_REQUIRED")

    @app.exception_handler(EvidenceError)
    async def evidence_failed(request: Any, exc: EvidenceError):
        from fastapi.responses import JSONResponse

        cell.orchestrator.stop()
        return JSONResponse(status_code=503, content={"detail": "EVIDENCE_UNAVAILABLE"})

    @app.exception_handler(PermissionError)
    async def permission_failed(request: Any, exc: PermissionError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid_request(request: Any, exc: ValueError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "alive", "mode": "SIL"}

    @app.get("/status", dependencies=[Depends(authenticated)])
    def status() -> dict[str, Any]:
        return cell.status()

    @app.post("/sessions", dependencies=[Depends(authenticated)])
    def login(body: Login) -> dict[str, str]:
        with cell.lock:
            return {"session_id": cell.access.login(body.operator_id, body.proof, cell.clock())}

    @app.post("/sessions/heartbeat", dependencies=[Depends(authenticated)])
    def heartbeat(body: SessionRequest) -> dict[str, bool]:
        with cell.lock:
            return {"accepted": cell.access.heartbeat(body.session_id, body.operator_id, cell.clock())}

    @app.post("/sessions/revoke", dependencies=[Depends(authenticated)])
    def revoke(body: SessionRequest) -> dict[str, bool]:
        with cell.lock:
            if not cell.access.authorize(body.session_id, body.operator_id, "inspect", cell.clock()):
                raise PermissionError("AUTHORITY_NOT_ADMITTED")
            cell.access.revoke(body.session_id)
            return {"accepted": True}

    @app.post("/tasks", dependencies=[Depends(authenticated)], response_model=TaskReceipt)
    def submit(body: MotionRequest) -> TaskReceipt:
        return cell.orchestrator.submit(body)

    @app.post("/tasks/{request_id}/cancel", dependencies=[Depends(authenticated)])
    def cancel(request_id: str, body: SessionRequest) -> TaskReceipt:
        return cell.orchestrator.cancel(request_id, body.session_id, body.operator_id)

    @app.post("/cycle", dependencies=[Depends(authenticated)])
    def cycle() -> TaskReceipt | None:
        return cell.orchestrator.run_next()

    @app.post("/simulation/observe", dependencies=[Depends(authenticated)])
    def observe() -> dict[str, Any]:
        cell.observe_simulation(cell.edge.last_seq + 1)
        return cell.status()

    @app.post("/stop", dependencies=[Depends(authenticated)])
    def stop() -> dict[str, Any]:
        # Stop is deliberately independent of the orchestrator execution lock.
        cell.orchestrator.stop()
        return {"stopped": True}

    @app.post("/reset", dependencies=[Depends(authenticated)])
    def reset(body: SessionRequest) -> dict[str, bool]:
        return {"accepted": cell.orchestrator.reset(body.session_id, body.operator_id)}

    @app.get("/analytics", dependencies=[Depends(authenticated)])
    def analytics() -> dict[str, Any]:
        return {"event_summary": cell.analytics.summary(), "sensor_trends": cell.analytics.sensor_trends()}

    @app.post("/resident", dependencies=[Depends(authenticated)])
    async def resident(body: Question) -> dict[str, Any]:
        with cell.lock:
            if not cell.access.authorize(body.session_id, body.operator_id, "inspect", cell.clock()):
                raise PermissionError("AUTHORITY_NOT_ADMITTED")
            state = cell.status()
        receipt = await cell.resident.ask(state, body.question)
        result = cell.resident_tool(receipt.proposal.action, body.session_id, body.operator_id) if receipt.proposal else None
        return {"receipt": receipt.model_dump(mode="json"), "tool_result": result}

    return app
