from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

CAPABILITY_COMMANDS = {
    "scaffoldctl.authority": "authority",
    "scaffoldctl.state_table": "state-table",
    "scaffoldctl.schema": "schema",
    "scaffoldctl.validate_root": "validate-root",
    "scaffoldctl.validate": "validate",
    "scaffoldctl.audit": "audit",
    "scaffoldctl.verify_ledger": "verify-ledger",
}
AUTHORITY_FIELDS = ("lease_id", "authority_tier", "agent_role")
EXACT_FIELDS = {
    "capability_id",
    "admission_epoch",
    "current_epoch",
    "lease_id",
    "authority_tier",
    "agent_role",
    "arguments",
}
MAX_ARGUMENTS = 24
MAX_ARGUMENT_CHARS = 512
MAX_TOTAL_ARGUMENT_CHARS = 4096
MAX_AUTHORITY_CHARS = 128
TIMEOUT_SECONDS = 30


def _bounded_text(value: Any, *, maximum: int) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum and "\x00" not in value


def _valid_epoch(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_request(request: dict[str, Any]) -> tuple[str, list[str]]:
    if not isinstance(request, dict) or set(request) != EXACT_FIELDS:
        raise ValueError("MCP_ADAPTER_SCHEMA_INVALID")
    if not _valid_epoch(request["admission_epoch"]) or not _valid_epoch(request["current_epoch"]):
        raise ValueError("MCP_EPOCH_INVALID")
    for field in AUTHORITY_FIELDS:
        if not _bounded_text(request[field], maximum=MAX_AUTHORITY_CHARS):
            raise PermissionError("MCP_PRESENT_AUTHORITY_REQUIRED")
    if request["admission_epoch"] != request["current_epoch"]:
        raise PermissionError("MCP_STALE_REMEMBERED_AFFORDANCE")
    capability = request["capability_id"]
    if not _bounded_text(capability, maximum=MAX_AUTHORITY_CHARS):
        raise PermissionError("MCP_CAPABILITY_NOT_ADMITTED")
    if capability not in CAPABILITY_COMMANDS:
        raise PermissionError("MCP_CAPABILITY_NOT_ADMITTED")
    arguments = request["arguments"]
    if not isinstance(arguments, list) or len(arguments) > MAX_ARGUMENTS:
        raise ValueError("MCP_ARGUMENT_BOUND_EXCEEDED")
    if any(not _bounded_text(item, maximum=MAX_ARGUMENT_CHARS) for item in arguments):
        raise ValueError("MCP_ARGUMENT_INVALID")
    if sum(map(len, arguments)) > MAX_TOTAL_ARGUMENT_CHARS:
        raise ValueError("MCP_ARGUMENT_BOUND_EXCEEDED")
    if capability in {"scaffoldctl.authority", "scaffoldctl.state_table"} and arguments:
        raise ValueError("MCP_ARGUMENT_INVALID")
    return CAPABILITY_COMMANDS[capability], arguments


def invoke(
    request: dict[str, Any],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    command, arguments = _validate_request(request)
    completed = runner(
        ["scaffoldctl", command, *arguments],
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=TIMEOUT_SECONDS,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "authority_ceiling": [
            "NO_DIRECT_ACTUATION",
            "NO_ARCHITECTURE_MUTATION",
            "NO_PROMOTION",
        ],
    }
