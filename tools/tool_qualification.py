"""Repeat upstream software regressions on the separately bound support copies."""

from __future__ import annotations

import asyncio
import json
import os
import sys

from ci_admission import ROOT


async def qualify(name: str) -> bool:
    source = ROOT / "vendor/qualified" / name
    out = ROOT / "evidence/ci/phase2/current"
    out.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--junitxml=" + str(out / (name + ".xml"))]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if name == "scaffoldctl":
        args.extend(["--cov=scaffoldctl", "--cov-fail-under=95",
                     "--cov-report=json:" + str(out / "scaffold-coverage.json")])
    process = await asyncio.create_subprocess_exec(*args, cwd=source, env=env,
                                                   stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.STDOUT)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), 120)
    except TimeoutError:
        process.kill()
        output, _ = await process.communicate()
        output += b"\nQUALIFICATION_TIMEOUT\n"
    (out / (name + ".log")).write_bytes(output)
    return process.returncode == 0


async def main() -> int:
    results = {name: await qualify(name) for name in ("scaffoldctl", "truth-serum")}
    path = ROOT / "evidence/ci/phase2/current/results.json"
    path.write_text(json.dumps({"regressions": results, "full_tool_admission": "HOLD",
                                "docker_build": "HOLD", "deployment": "HOLD"}, indent=2) + "\n")
    print(json.dumps(results))
    if not all(results.values()):
        print("::error::Reusable tool regression failed; inspect phase2/current")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
