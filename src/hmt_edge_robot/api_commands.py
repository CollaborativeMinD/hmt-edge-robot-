"""api: commands interface."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import ValidationError

from .api_requests import Login, SessionRequest
from .contracts import MotionRequest, TaskReceipt
from .runtime import RobotCell


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
