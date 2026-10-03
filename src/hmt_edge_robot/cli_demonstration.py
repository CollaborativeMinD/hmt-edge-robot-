"""cli: demonstration interface."""

from __future__ import annotations

import asyncio
import secrets

from .contracts import MotionRequest
from .runtime import RobotCell
from .vision import synthetic_frame


def demonstrate(cell: RobotCell, token: str) -> dict:
    session = cell.access.login("operator", token, cell.clock())
    cell.observe_simulation(cell.edge.last_seq + 1)
    candidates = cell.vision.candidates(synthetic_frame())
    cell.ledger.append("vision", "demo", "grasp_observation", candidates[0].model_dump(mode="json"))
    now = cell.clock()
    request = MotionRequest(
        request_id="demo-" + secrets.token_hex(8),
        operator_id="operator",
        session_id=session,
        policy_epoch=cell.policy.policy_epoch,
        target_mm=candidates[0].target_mm,
        speed_mps=0.1,
        issued_at=now,
        expires_at=now + cell.policy.max_command_age_sec,
    )
    planned = cell.orchestrator.submit(request)
    outcome = cell.orchestrator.run_next()
    resident = asyncio.run(cell.resident.ask(cell.status(), "Inspect the mission outcome."))
    baseline = tuple((4.05 + (i % 7) * 0.01, 44.0 + (i % 5) * 0.3) for i in range(32))
    cell.resident.health_model.fit(baseline)
    health = cell.resident.health_model.predict(3.2, 90.0)
    cell.ledger.append(
        "resident",
        "demo",
        "ml_diagnostic",
        {"classification": "SYNTHETIC_SIL_BASELINE", "result": health},
    )
    return {
        "mode": "SIL",
        "planned": planned.model_dump(mode="json"),
        "outcome": outcome.model_dump(mode="json") if outcome else None,
        "resident": resident.model_dump(mode="json"),
        "health_model": health,
        "verified_events": cell.ledger.verify(),
    }
