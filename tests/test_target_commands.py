"""REQ-CD5-02: true subprocess bounds, failures and fixed command admission."""
from __future__ import annotations

import os
import sys

import pytest
import target_commands


@pytest.mark.parametrize("script,reason", [("print('ok')", "COMMAND_COMPLETED"), ("raise SystemExit(3)", "COMMAND_FAILED"), ("print('x'*70000)", "COMMAND_OUTPUT_LIMIT"), ("print('x'*10000000)", "COMMAND_OUTPUT_LIMIT"), ("import time;time.sleep(10)", "COMMAND_TIMEOUT")])
def test_command_bounds(monkeypatch: pytest.MonkeyPatch, script: str, reason: str) -> None:
    monkeypatch.setitem(target_commands.COMMANDS, "test", (sys.executable, "-c", script))
    monkeypatch.setattr(target_commands, "TIMEOUT_SECONDS", 0.2)
    probe = target_commands.execute("test")
    assert probe.reason_code == reason and len(probe.output) <= 65536
    assert (probe.status == "PASS") == (reason == "COMMAND_COMPLETED")


def test_missing_command_and_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(target_commands.COMMANDS, "test", ("/no/such/tool",))
    assert target_commands.execute("test").reason_code == "COMMAND_UNAVAILABLE"
    with pytest.raises(KeyError):
        target_commands.execute("sh -c arbitrary")
    assert not any("install" in command or "apply" in command or "up" in command for argv in target_commands.COMMANDS.values() for command in argv)


def test_output_limit_reaps_process_group(monkeypatch: pytest.MonkeyPatch) -> None:
    script = "import os,time;print(os.getpid(),flush=True);print('x'*70000,flush=True);time.sleep(10)"
    monkeypatch.setitem(target_commands.COMMANDS, "test", (sys.executable, "-c", script))
    probe = target_commands.execute("test")
    assert probe.reason_code == "COMMAND_OUTPUT_LIMIT"
    pid = int(probe.output.splitlines()[0])
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
