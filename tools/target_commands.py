"""REQ-CD5-02: fixed read-only command surface; bounded pipe and process lifetime."""
from __future__ import annotations

import asyncio
import os
import signal

from target_contracts import Probe

COMMANDS: dict[str, tuple[str, ...]] = {
    "hostname": ("/usr/bin/hostname",),
    "kernel": ("/usr/bin/uname", "-r"),
    "architecture": ("/usr/bin/uname", "-m"),
    "userspace_bits": ("/usr/bin/getconf", "LONG_BIT"),
    "blocks": ("/usr/bin/lsblk", "--json", "--bytes", "--output", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS", "/dev/mmcblk0"),
    "tailscale_version": ("/usr/bin/tailscale", "version"),
    "tailscale_ipv4": ("/usr/bin/tailscale", "ip", "-4"),
    "k3s_server": ("/usr/bin/systemctl", "is-active", "k3s"),
    "k3s_agent": ("/usr/bin/systemctl", "is-active", "k3s-agent"),
    "k3s_version": ("/usr/local/bin/k3s", "--version"),
    "flux_version": ("/usr/local/bin/flux", "version", "--client"),
}
REQUIRED = frozenset(COMMANDS) - {"k3s_server", "k3s_agent", "k3s_version", "flux_version"}
TIMEOUT_SECONDS = 5


async def run_command(name: str) -> Probe:
    data = bytearray()
    reason = "COMMAND_COMPLETED"
    try:
        proc = await asyncio.create_subprocess_exec(*COMMANDS[name], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, stdin=asyncio.subprocess.DEVNULL, start_new_session=True, env={"PATH": "/usr/bin:/usr/local/bin", "LC_ALL": "C"})
    except OSError:
        return Probe(name=name, status="FAIL", output="", reason_code="COMMAND_UNAVAILABLE")
    try:
        if proc.stdout is None:
            raise RuntimeError("COLLECTOR_PIPE_UNAVAILABLE")
        async with asyncio.timeout(TIMEOUT_SECONDS):
            while block := await proc.stdout.read(4096):
                if len(data) + len(block) > 65536:
                    reason = "COMMAND_OUTPUT_LIMIT"
                    break
                data.extend(block)
            if reason == "COMMAND_COMPLETED":
                await proc.wait()
            if proc.returncode != 0 and reason == "COMMAND_COMPLETED":
                reason = "COMMAND_FAILED"
    except TimeoutError:
        reason = "COMMAND_TIMEOUT"
    finally:
        if proc.returncode is None or reason != "COMMAND_COMPLETED":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        async with asyncio.timeout(5):
            if proc.stdout is not None:
                while await proc.stdout.read(4096):
                    pass
            await proc.wait()
    return Probe.model_validate({"name": name, "status": "PASS" if reason == "COMMAND_COMPLETED" else "FAIL", "output": data.decode("utf-8", errors="replace"), "reason_code": reason})


def execute(name: str) -> Probe:
    return asyncio.run(run_command(name))
