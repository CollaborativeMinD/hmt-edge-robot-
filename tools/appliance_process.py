"""Fixed executable argv, bounded waits, and reaped failures for appliance tooling."""
from __future__ import annotations

import asyncio
import subprocess


async def execute(args: list[str], timeout: int) -> bytes:
    if not args or not args[0].startswith("/"):
        raise ValueError("ABSOLUTE_EXECUTABLE_REQUIRED")
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.PIPE)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        raise
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode or 1, args[0])
    if len(output) > 2**20:
        raise ValueError("PROCESS_OUTPUT_TOO_LARGE")
    return output


def run(args: list[str], timeout: int = 30) -> bytes:
    return asyncio.run(execute(args, timeout))
