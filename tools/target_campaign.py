"""REQ-CD5-05: cumulative negative evidence, fail closed before process creation."""
from __future__ import annotations

import asyncio
import json
import os
import sys

from ci_admission import ROOT
from target_io import atomic_write


async def main() -> int:
    directory = ROOT / "evidence/cd/stage5"
    destination = directory / "campaign.json"
    failure = {"status": "FAIL", "target_qualification": "HOLD", "deployment": "HOLD", "reason_codes": ["TARGET_CAMPAIGN_INCOMPLETE"], "alert": True}
    atomic_write(destination, failure)
    args = [sys.executable, "-m", "pytest", "-q", *[str(p.relative_to(ROOT)) for p in sorted((ROOT / "tests").glob("test_target_*.py"))], "--cov-fail-under=90", "--cov-report=json:" + str(directory / "coverage.json"), "--cov-report=term-missing", "--junitxml=" + str(directory / "tests.xml")]
    args += ["--cov=" + p.stem for p in sorted((ROOT / "tools").glob("target_*.py"))]
    env = dict(os.environ, COVERAGE_FILE=str(directory / ".coverage"))
    output = b"TARGET_CAMPAIGN_SPAWN_FAILED\n"
    status = "FAIL"
    try:
        process = await asyncio.create_subprocess_exec(*args, cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(process.communicate(), 60)
            status = "PASS" if process.returncode == 0 else "FAIL"
        except TimeoutError:
            process.kill()
            output, _ = await asyncio.wait_for(process.communicate(), 5)
            output += b"\nTARGET_CAMPAIGN_TIMEOUT\n"
    except (OSError, TimeoutError):
        status = "FAIL"
    (directory / "negative_tests.log").write_bytes(output)
    result = {**failure, "status": status, "reason_codes": ["TARGET_SOFTWARE_TESTS_" + status], "alert": status != "PASS"}
    atomic_write(destination, result)
    print(json.dumps(result))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
