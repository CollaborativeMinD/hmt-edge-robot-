"""Compatibility facade for the decomposed cli interfaces."""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
from pathlib import Path

from .cli_commands import dispatch as dispatch
from .cli_commands import serve as serve
from .cli_demonstration import demonstrate as demonstrate
from .contracts import Policy
from .resident import OpenAICompatibleProvider
from .runtime import RobotCell


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "command", choices=("demo", "replay", "analytics", "export", "resident", "serve")
    )
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
    read_only = args.command in ("replay", "analytics", "export")
    cell = RobotCell(args.database, token, policy, read_only=read_only)
    try:
        if args.model_url or args.model_id:
            if read_only:
                raise SystemExit("Read-only commands cannot activate a model")
            if not (args.model_url and args.model_id):
                raise SystemExit("Both --model-url and --model-id are required")
            provider = OpenAICompatibleProvider(
                args.model_url, args.model_id, policy, os.environ.get("HMT_MODEL_KEY")
            )
            cell.resident.provider = provider
            receipt = asyncio.run(provider.qualify(cell.resident.context(cell.status())))
            cell.ledger.append(
                "resident", provider.model_id, "model_qualification", {"artifact_hash": receipt}
            )
        dispatch(args, cell, token)
    finally:
        cell.close()

if __name__ == "__main__":
    main()
