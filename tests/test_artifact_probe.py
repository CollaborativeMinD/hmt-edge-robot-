"""Installed mission probe carries real composition behavior into the image harness."""
from __future__ import annotations

from pathlib import Path

import pytest
from artifact_probe import run


def test_probe_requires_runtime_only_installation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="DEVELOPMENT_TOOLS_IN_RUNTIME"):
        run(tmp_path)


def test_probe_composed_outcome_replay_and_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("artifact_probe.importlib.metadata.distributions", lambda: [])
    result = run(tmp_path)
    assert result["events"] == result["replayed"] > 0
    assert result["simulated_moves"] == 1 and result["paid_calls"] == 0
    assert result["resident_stopped"] is True
