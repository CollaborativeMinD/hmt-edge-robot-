"""A hung or unstartable test process cannot leave a prior PASS campaign."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import artifact_campaign as campaign
import pytest


@pytest.mark.parametrize("behavior", ["timeout", "failed", "success", "spawn_error"])
def test_artifact_campaign_timeout_and_startup_failure_preserve_fail_closed_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, behavior: str) -> None:
    output = tmp_path / "evidence/cd/stage4"
    output.mkdir(parents=True)
    destination = output / "campaign.json"
    destination.write_text('{"status": "PASS"}')
    monkeypatch.setattr(campaign, "ROOT", tmp_path)

    class Process:
        returncode: int = 0 if behavior == "success" else 1
        killed = False

        async def communicate(self) -> tuple[bytes, None]:
            if behavior == "timeout" and not self.killed:
                raise TimeoutError("simulated hung pytest")
            return b"simulated pytest outcome", None

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    process = Process()

    async def create(*args, **kwargs) -> Process:
        assert json.loads(destination.read_text())["status"] == "FAIL"
        if behavior == "spawn_error":
            raise OSError("simulated executable unavailable")
        return process

    monkeypatch.setattr(campaign.asyncio, "create_subprocess_exec", create)
    if behavior == "spawn_error":
        with pytest.raises(OSError, match="unavailable"):
            asyncio.run(campaign.main())
    else:
        assert asyncio.run(campaign.main()) == (0 if behavior == "success" else 1)
    result = json.loads(destination.read_text())
    assert result["status"] == ("PASS" if behavior == "success" else "FAIL")
    assert result["release_decision"] == result["cluster_deployment"] == "HOLD"
    if behavior == "timeout":
        assert process.killed and "STAGE4_TEST_TIMEOUT" in (output / "negative_tests.log").read_text()
