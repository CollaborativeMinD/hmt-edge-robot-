"""api: queries interface."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from .api_requests import SessionRequest
from .ledger import EvidenceError
from .runtime import RobotCell


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
