"""Fail-closed external witness execution."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .external_exec import execution_error, invoke, write_raw
from .lanes import lane
from .models import AdmissionMode, Decision, Finding, LaneReport, LaneStatus
from .policy import PolicyError, requires_external
from .witness_json import classify
from .witnesses import TOOLS, has_target


def run_all(mode: AdmissionMode, root: Path, out: Path) -> tuple[LaneReport, ...]:
    try:
        required = requires_external(root / "contracts/lane_policy.yaml", mode)
    except PolicyError:
        required = True
    return tuple(_run(tool, root, out, required) for tool in TOOLS)


def _run(tool: str, root: Path, out: Path, required: bool) -> LaneReport:
    lane_id = f"witness-{tool}"
    code_tool = tool.upper().replace("-", "_")
    if not required:
        return lane(
            lane_id,
            LaneStatus.NOT_APPLICABLE,
            tool,
            (f"NOT_APPLICABLE_WITNESS_{code_tool}",),
            required=False,
        )
    if not has_target(tool, root):
        return lane(
            lane_id, LaneStatus.NOT_APPLICABLE, tool, (f"NOT_APPLICABLE_WITNESS_{code_tool}",)
        )
    if shutil.which(tool) is None:
        return lane(
            lane_id, LaneStatus.UNAVAILABLE, tool, (f"HOLD_WITNESS_{code_tool}_UNAVAILABLE",)
        )
    try:
        result = invoke(tool, root, out)
    except (OSError, subprocess.TimeoutExpired) as error:
        finding = Finding(
            reason_code=f"HOLD_WITNESS_{code_tool}_ERROR",
            message=type(error).__name__,
            route=Decision.HOLD,
        )
        return lane(lane_id, LaneStatus.ERROR, tool, (finding.reason_code,), (finding,))
    refs = write_raw(tool, out, result.stdout, result.stderr)
    native_state = classify(tool, result.stdout)
    if native_state == "ERROR":
        code = f"HOLD_WITNESS_{code_tool}_ERROR"
        finding = Finding(
            reason_code=code,
            message="Native JSON output is malformed or partial.",
            route=Decision.HOLD,
        )
        return lane(lane_id, LaneStatus.ERROR, tool, (code,), (finding,), refs)
    if execution_error(tool, result.returncode):
        code = f"HOLD_WITNESS_{code_tool}_ERROR"
        finding = Finding(
            reason_code=code,
            message=f"Witness execution returned {result.returncode}.",
            route=Decision.HOLD,
        )
        return lane(lane_id, LaneStatus.ERROR, tool, (code,), (finding,), refs)
    if native_state == "FINDING":
        code = f"FAIL_WITNESS_{code_tool}_FINDING"
        finding = Finding(reason_code=code, message="Native JSON output contains findings.")
        return lane(lane_id, LaneStatus.FAIL, tool, (code,), (finding,), refs)
    if result.returncode == 0:
        return lane(lane_id, LaneStatus.PASS, tool, (f"PASS_WITNESS_{code_tool}",), evidence=refs)
    code = f"FAIL_WITNESS_{code_tool}_FINDING"
    finding = Finding(reason_code=code, message=f"Witness returned {result.returncode}.")
    return lane(lane_id, LaneStatus.FAIL, tool, (code,), (finding,), refs)
