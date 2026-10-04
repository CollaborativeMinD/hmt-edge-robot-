"""Release signing never preserves stale success when fresh artifact admission fails."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest
from appliance_process import execute, run
from appliance_release import release


def test_failed_requalification_invalidates_old_signed_release(tmp_path: Path) -> None:
    directory = tmp_path / "build/release"
    directory.mkdir(parents=True)
    (directory / "release.json").write_text('{"status":"PASS"}')
    (directory / "release.sig").write_bytes(b"old")
    with pytest.raises(ValueError, match="OCI_ARCHIVE_UNAVAILABLE"):
        release(tmp_path, "1" * 40)
    assert not (directory / "release.sig").exists()
    assert '"FAIL"' in (directory / "release.json").read_text()


def test_appliance_process_reaps_timeout_and_rejects_failures() -> None:
    assert run(["/usr/bin/printf", "checked"]) == b"checked"
    with pytest.raises(ValueError, match="ABSOLUTE"):
        run(["printf", "unsafe-path"])
    with pytest.raises(subprocess.CalledProcessError):
        run(["/usr/bin/false"])
    with pytest.raises(TimeoutError):
        asyncio.run(execute(["/usr/bin/sleep", "2"], 1))


def test_firstboot_example_contains_no_real_credentials() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "deploy/appliance/node.example.json").read_text()
    assert "REPLACE_WITH" in text and "PRIVATE KEY" not in text
    assert os.environ.get("HMT_SIGNING_PRIVATE_KEY") is None
