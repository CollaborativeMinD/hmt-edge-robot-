"""REQ-UI-02: runnable demonstration, replay, analytics, resident, and private API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path

from .contracts import MotionRequest, Policy, canonical
from .resident import OpenAICompatibleProvider
from .runtime import RobotCell
from .vision import synthetic_frame


def demonstrate(cell: RobotCell, token: str) -> dict:
    session = cell.access.login("operator", token, cell.clock())
    cell.observe_simulation(cell.edge.last_seq + 1)
    candidates = cell.vision.candidates(synthetic_frame())
    cell.ledger.append("vision", "demo", "grasp_observation", candidates[0].model_dump(mode="json"))
    now = cell.clock()
    request = MotionRequest(request_id="demo-" + secrets.token_hex(8), operator_id="operator", session_id=session,
                            policy_epoch=cell.policy.policy_epoch, target_mm=candidates[0].target_mm, speed_mps=0.1,
                            issued_at=now, expires_at=now + cell.policy.max_command_age_sec)
    planned = cell.orchestrator.submit(request)
    outcome = cell.orchestrator.run_next()
    resident = asyncio.run(cell.resident.ask(cell.status(), "Inspect the mission outcome."))
    baseline = tuple((4.05 + (i % 7) * 0.01, 44.0 + (i % 5) * 0.3) for i in range(32))
    cell.resident.health_model.fit(baseline)
    health = cell.resident.health_model.predict(3.2, 90.0)
    cell.ledger.append("resident", "demo", "ml_diagnostic", {"classification": "SYNTHETIC_SIL_BASELINE", "result": health})
    return {"mode": "SIL", "planned": planned.model_dump(mode="json"),
            "outcome": outcome.model_dump(mode="json") if outcome else None,
            "resident": resident.model_dump(mode="json"), "health_model": health,
            "verified_events": cell.ledger.verify()}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("demo", "replay", "analytics", "export", "resident", "serve"))
    result.add_argument("--database", type=Path, default=Path("runtime/cell.db"))
    result.add_argument("--output", type=Path, default=Path("runtime/evidence.parquet"))
    result.add_argument("--question", default="Inspect current evidence.")
    result.add_argument("--policy", type=Path)
    result.add_argument("--model-url")
    result.add_argument("--model-id")
    result.add_argument("--port", type=int, default=8000)
    return result


def main() -> None:
    args = parser().parse_args()
    policy = Policy.model_validate_json(args.policy.read_text()) if args.policy else Policy()
    token = os.environ.get("HMT_OPERATOR_TOKEN")
    if args.command in ("serve", "resident") and (token is None or len(token) < 16):
        raise SystemExit("HMT_OPERATOR_TOKEN must contain at least 16 characters")
    token = token or secrets.token_hex(32)
    cell = RobotCell(args.database, token, policy)
    try:
        if args.model_url or args.model_id:
            if not (args.model_url and args.model_id):
                raise SystemExit("Both --model-url and --model-id are required")
            provider = OpenAICompatibleProvider(args.model_url, args.model_id, policy, os.environ.get("HMT_MODEL_KEY"))
            receipt = asyncio.run(provider.qualify(cell.resident.context(cell.status())))
            cell.ledger.append("resident", provider.model_id, "model_qualification", {"artifact_hash": receipt})
            cell.resident.provider = provider
        dispatch(args, cell, token)
    finally:
        cell.close()


def dispatch(args: argparse.Namespace, cell: RobotCell, token: str) -> None:
    if args.command == "demo":
        output = demonstrate(cell, token)
    elif args.command == "replay":
        output = {"verified_events": cell.ledger.verify(), "tail": cell.ledger.recent()}
    elif args.command == "analytics":
        output = {"event_summary": cell.analytics.summary(), "sensor_trends": cell.analytics.sensor_trends()}
    elif args.command == "export":
        output = {"exported_records": cell.analytics.export_parquet(args.output), "path": str(args.output)}
    elif args.command == "resident":
        session = cell.access.login("operator", token, cell.clock())
        receipt = asyncio.run(cell.resident.ask(cell.status(), args.question))
        tool = cell.resident_tool(receipt.proposal.action, session, "operator") if receipt.proposal else None
        output = {"receipt": receipt.model_dump(mode="json"), "tool_result": tool}
    else:
        serve(args, cell)
        return
    print(json.dumps(output, indent=2, allow_nan=False))


def serve(args: argparse.Namespace, cell: RobotCell) -> None:
    import uvicorn

    from .api import create_app

    api_token = os.environ.get("HMT_API_TOKEN", "")
    if len(api_token) < 16:
        raise SystemExit("HMT_API_TOKEN must contain at least 16 characters")
    uvicorn.run(create_app(cell, api_token), host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
