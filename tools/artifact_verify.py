"""Independent cryptographic verification; caller-supplied JSON is never sufficient."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

REPOSITORY = "CollaborativeMinD/hmt-edge-robot-"


async def verify(archive: Path, commit: str) -> bytes:
    process = await asyncio.create_subprocess_exec("/usr/bin/gh", "attestation", "verify",
        str(archive), "--repo", REPOSITORY, "--signer-workflow",
        REPOSITORY + "/.github/workflows/artifact.yml", "--source-digest", commit,
        "--format", "json", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), 90)
    except TimeoutError:
        process.kill()
        await asyncio.wait_for(process.wait(), 5)
        raise
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode or 1, "gh attestation verify")
    return output


def verify_signature(archive: Path, commit: str) -> object:
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("PROVENANCE_SOURCE_COMMIT_REQUIRED")
    output = asyncio.run(verify(archive, commit))
    if len(output) > 2**20:
        raise ValueError("PROVENANCE_VERIFICATION_TOO_LARGE")
    value = json.loads(output)
    temporary = archive.parent / "provenance-verification.tmp"
    temporary.write_bytes(output)
    temporary.replace(archive.parent / "provenance-verification.json")
    return value
