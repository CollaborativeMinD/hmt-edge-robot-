"""validate: execution interface."""

from __future__ import annotations

import asyncio
import sqlite3

from validate_base import ROOT, RUN
from validate_ledger import record


async def execute(db: sqlite3.Connection, gate: str, requirement: str, args: list[str]) -> bool:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        process.kill()
        output, _ = await process.communicate()
        output += b"\nVERIFICATION_TIMEOUT\n"
    path = RUN / (gate + ".log")
    path.write_bytes(output)
    passed = process.returncode == 0
    record(db, gate, requirement, "PASS" if passed else "FAIL", path)
    print(gate, "PASS" if passed else "FAIL", flush=True)
    return passed
