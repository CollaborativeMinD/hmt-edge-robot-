"""cli: commands interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from .cli_demonstration import demonstrate
from .runtime import RobotCell


def dispatch(args: argparse.Namespace, cell: RobotCell, token: str) -> None:
    if args.command == "demo":
        output = demonstrate(cell, token)
    elif args.command == "replay":
        output = {"verified_events": cell.ledger.verify(), "tail": cell.ledger.recent()}
    elif args.command == "analytics":
        output = {
            "event_summary": cell.analytics.summary(),
            "sensor_trends": cell.analytics.sensor_trends(),
        }
    elif args.command == "export":
        output = {
            "exported_records": cell.analytics.export_parquet(args.output),
            "path": str(args.output),
        }
    elif args.command == "resident":
        session = cell.access.login("operator", token, cell.clock())
        receipt = asyncio.run(cell.resident.ask(cell.status(), args.question))
        tool = (
            cell.resident_tool(receipt.proposal.action, session, "operator")
            if receipt.proposal
            else None
        )
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
