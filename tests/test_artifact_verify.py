"""Verification invokes cryptographic gh checks with a deadline and source fence."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from artifact_support import COMMIT
from artifact_verify import verify_signature


class Process:
    def __init__(self, code: int = 0, output: bytes = b'[{"verified":true}]', timeout: bool = False) -> None:
        self.returncode, self.output, self.timeout = code, output, timeout
        self.killed = False
    async def communicate(self) -> tuple[bytes, bytes]:
        if self.timeout:
            raise TimeoutError()
        return self.output, b""
    def kill(self) -> None:
        self.killed = True
    async def wait(self) -> int:
        return self.returncode


def patch(monkeypatch: pytest.MonkeyPatch, process: Process) -> None:
    async def verified(*args: object, **kwargs: object) -> Process:
        assert args[0] == "/usr/bin/gh" and "--source-digest" in args and COMMIT in args
        assert "--signer-workflow" in args
        return process
    monkeypatch.setattr("artifact_verify.asyncio.create_subprocess_exec", verified)


def test_verifier_requires_source_digest_and_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch(monkeypatch, Process())
    assert verify_signature(tmp_path / "image.oci.tar", COMMIT) == [{"verified": True}]
    assert json.loads((tmp_path / "provenance-verification.json").read_text()) == [{"verified": True}]


@pytest.mark.parametrize("commit", ["", "main", "x" * 40])
def test_invalid_commit_prevents_external_verification(tmp_path: Path, commit: str) -> None:
    with pytest.raises(ValueError, match="SOURCE_COMMIT"):
        verify_signature(tmp_path / "image.oci.tar", commit)


@pytest.mark.parametrize("code,output,timeout", [(1, b"denied", False), (0, b"x" * (2**20 + 1), False), (0, b"", True)], ids=["nonzero", "oversize", "timeout"])
def test_failed_hung_or_oversized_verifier_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, output: bytes, timeout: bool) -> None:
    process = Process(code, output, timeout)
    patch(monkeypatch, process)
    with pytest.raises((ValueError, TimeoutError, subprocess.SubprocessError)):
        verify_signature(tmp_path / "image.oci.tar", COMMIT)
    assert process.killed == timeout
