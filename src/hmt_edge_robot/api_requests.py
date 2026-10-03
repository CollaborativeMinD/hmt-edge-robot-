"""api: requests interface."""

from __future__ import annotations

from pydantic import Field

from .contracts import Contract, Identifier


class Login(Contract):
    operator_id: Identifier
    proof: str = Field(min_length=1, max_length=256)

class SessionRequest(Contract):
    session_id: Identifier
    operator_id: Identifier

class Question(SessionRequest):
    question: str = Field(min_length=1, max_length=2048)
