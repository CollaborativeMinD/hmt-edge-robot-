"""REQ-AM-01..03: explicit permissions, leases, revocation; no badge-prefix authority."""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass
from typing import Protocol

from .contracts import Policy, digest
from .ledger import Ledger


class IdentityProvider(Protocol):
    def authenticate(self, operator_id: str, proof: str) -> tuple[str, ...]: ...


class ProvisionedIdentity:
    """Local token adapter. This is one factor; external MFA belongs in an adapter."""

    def __init__(self, entries: dict[str, tuple[str, tuple[str, ...]]]) -> None:
        self.entries = dict(entries)

    def authenticate(self, operator_id: str, proof: str) -> tuple[str, ...]:
        entry = self.entries.get(operator_id)
        if entry is None or not secrets.compare_digest(entry[0], digest(proof)):
            return ()
        return entry[1]


@dataclass(frozen=True)
class Session:
    session_id: str
    operator_id: str
    permissions: tuple[str, ...]
    created_at: float
    last_presence_time: float
    policy_epoch: int


class AccessManager:
    def __init__(self, provider: IdentityProvider, policy: Policy, ledger: Ledger) -> None:
        self.provider, self.policy, self.ledger = provider, policy, ledger
        self.sessions: dict[str, Session] = {}
        self.last_clock = 0.0

    def _clock(self, now: float) -> None:
        if not math.isfinite(now) or now < self.last_clock:
            self.sessions.clear()
            raise ValueError("CLOCK_REGRESSION")
        self.last_clock = now

    def login(self, operator_id: str, proof: str, now: float) -> str:
        self._clock(now)
        permissions = self.provider.authenticate(operator_id, proof)
        if not permissions:
            self.ledger.append("access", operator_id, "login_denied", {"rejection_reason": "IDENTITY_NOT_VERIFIED"})
            raise PermissionError("IDENTITY_NOT_VERIFIED")
        expired = [key for key, session in self.sessions.items() if now - session.created_at >= self.policy.session_timeout_sec]
        for key in expired:
            self.revoke(key)
        if len(self.sessions) >= self.policy.max_queue_size:
            raise PermissionError("SESSION_CAPACITY_EXHAUSTED")
        session_id = secrets.token_hex(16)
        self.ledger.append("access", operator_id, "session_created", {"session_id": session_id, "permissions": permissions, "policy_epoch": self.policy.policy_epoch})
        self.sessions[session_id] = Session(session_id, operator_id, permissions, now, now, self.policy.policy_epoch)
        return session_id

    def authorize(self, session_id: str, operator_id: str, permission: str, now: float) -> bool:
        self._clock(now)
        session = self.sessions.get(session_id)
        if session is None or session.operator_id != operator_id:
            return False
        if session.policy_epoch != self.policy.policy_epoch:
            return False
        expired = now - session.created_at >= self.policy.session_timeout_sec
        absent = now - session.last_presence_time >= self.policy.heartbeat_timeout_sec
        return not (expired or absent) and permission in session.permissions

    def heartbeat(self, session_id: str, operator_id: str, now: float) -> bool:
        self._clock(now)
        session = self.sessions.get(session_id)
        if session is None or not self.authorize(session_id, operator_id, "inspect", now):
            return False
        self.ledger.append("access", operator_id, "presence_confirmed", {"session_id": session_id})
        self.sessions[session_id] = Session(session_id, operator_id, session.permissions, session.created_at, now, session.policy_epoch)
        return True

    def revoke(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.ledger.append("access", session_id, "session_revoked", {"session_id": session_id})
