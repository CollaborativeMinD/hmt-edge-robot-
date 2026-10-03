"""Repeat the bounded stage-3 adversarial suite with branch coverage evidence."""

from __future__ import annotations

import asyncio
import json
import os
import sys

from ci_admission import ROOT


async def main() -> int:
    output_dir = ROOT / "evidence/cd/stage3"
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "campaign.json"
    destination.write_text(json.dumps({"status": "FAIL", "release_decision": "HOLD",
        "docker_execution": "HOLD", "cluster_deployment": "HOLD",
        "notification": "STAGE3_TESTS_NOT_COMPLETED", "alert": True}, indent=2) + "\n")
    args = [sys.executable, "-m", "pytest", "-q", *[str(p.relative_to(ROOT)) for p in sorted((ROOT / "tests").glob("test_deployment*.py"))],
            "--cov-fail-under=90", "--cov-report=json:" + str(output_dir / "coverage.json"),
            "--cov-report=term-missing", "--junitxml=" + str(output_dir / "tests.xml")]
    args += ["--cov=" + p.stem for p in sorted((ROOT / "tools").glob("deployment_*.py"))]
    env = dict(os.environ, COVERAGE_FILE=str(output_dir / ".coverage"))
    process = await asyncio.create_subprocess_exec(*args, cwd=ROOT, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), 60)
    except TimeoutError:
        process.kill()
        output, _ = await asyncio.wait_for(process.communicate(), 5)
        output += b"\nSTAGE3_TEST_TIMEOUT\n"
    (output_dir / "negative_tests.log").write_bytes(output)
    status = "PASS" if process.returncode == 0 else "FAIL"
    report = {"status": status, "release_decision": "HOLD", "docker_execution": "HOLD",
              "cluster_deployment": "HOLD", "notification": "STAGE3_NEGATIVE_TESTS_" + status,
              "alert": status != "PASS"}
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)
    print(json.dumps(report))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
