"""api: resident interface."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, FastAPI

from .api_requests import Question
from .runtime import RobotCell


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
