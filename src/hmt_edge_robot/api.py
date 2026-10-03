"""Compatibility facade for the decomposed api interfaces."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException

from .api_commands import session_routes as session_routes
from .api_commands import task_routes as task_routes
from .api_queries import error_routes as error_routes
from .api_queries import read_routes as read_routes
from .api_requests import Login as Login
from .api_requests import Question as Question
from .api_requests import SessionRequest as SessionRequest
from .api_resident import resident_routes as resident_routes
from .assurance.routes import routes as assurance_routes
from .ingress import BoundedIngress
from .runtime import RobotCell


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
    assurance_routes(app, cell, authenticated)
    return app
