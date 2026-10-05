"""Slow qualification work cannot reuse an expired operator-presence session."""
from __future__ import annotations

import asyncio
from pathlib import Path

import assurance_campaign
import pytest

from hmt_edge_robot.runtime import RobotCell


def test_campaign_reauthenticates_after_scale_expires_presence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    original_scale = assurance_campaign.scale

    def cell(database: Path, token: str) -> RobotCell:
        return RobotCell(database, token, clock=lambda: now[0])

    def slow_scale(runtime: RobotCell) -> dict:
        report = original_scale(runtime)
        now[0] += 2.0
        return report

    monkeypatch.setattr(assurance_campaign, "RobotCell", cell)
    monkeypatch.setattr(assurance_campaign, "scale", slow_scale)
    monkeypatch.setattr(assurance_campaign, "OUTPUT", tmp_path / "exports")
    report = asyncio.run(assurance_campaign.campaign(tmp_path))
    assert report["status"] == "PASS" and report["driver_moves"] == 0
