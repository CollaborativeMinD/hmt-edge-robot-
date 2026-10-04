"""REQ-CD5-05: campaign failure cannot retain a prior PASS receipt."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import target_campaign


class Process:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.returncode = 0 if mode == "pass" else 1
        self.calls = 0

    async def communicate(self) -> tuple[bytes, None]:
        self.calls += 1
        if self.mode == "timeout" and self.calls == 1:
            raise TimeoutError
        return b"bounded log\n", None

    def kill(self) -> None:
        self.returncode = -9


@pytest.mark.parametrize("mode", ["pass", "fail", "spawn", "timeout"])
def test_campaign_invalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setattr(target_campaign, "ROOT", tmp_path)
    destination = tmp_path / "evidence/cd/stage5/campaign.json"
    destination.parent.mkdir(parents=True)
    destination.write_text('{"status":"PASS"}')
    async def spawn(*args: object, **kwargs: object) -> Process:
        assert json.loads(destination.read_text())["status"] == "FAIL"
        if mode == "spawn":
            raise OSError("unavailable")
        return Process(mode)
    monkeypatch.setattr(target_campaign.asyncio, "create_subprocess_exec", spawn)
    assert asyncio.run(target_campaign.main()) == (0 if mode == "pass" else 1)
    assert json.loads(destination.read_text())["status"] == ("PASS" if mode == "pass" else "FAIL")
