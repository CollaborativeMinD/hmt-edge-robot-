"""REQ-CD4-03: source, artifact, scanner, and signature contradictions fail closed."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from artifact_gate import evaluate, main
from artifact_support import COMMIT, fixture, signature


def verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    def verified(archive: Path, commit: str) -> object:
        value = signature(archive)
        (archive.parent / "provenance-verification.json").write_text(json.dumps(value))
        return value
    monkeypatch.setattr("artifact_gate.verify_signature", verified)


def test_artifact_qualification_is_replayable_and_source_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture(tmp_path)
    verifier(monkeypatch)
    first = evaluate(tmp_path, COMMIT)
    assert first == evaluate(tmp_path, COMMIT)
    assert first.deployment == "HOLD" and first.hardware == "HOLD"
    assert main(tmp_path, COMMIT) == 0


@pytest.mark.parametrize("name,mutation", [
    ("base-lock.json", {"python": "latest"}), ("scan-input.json", {"Digest": "wrong"}),
    ("sbom.spdx.json", {}), ("vulnerabilities.json", {}),
    ("container.json", {"status": "PASS", "uid": 0}),
    ("loaded-image.json", [{"Id": "sha256:" + "4" * 64}]),
    ("build-metadata.json", {"containerimage.config.digest": "sha256:" + "4" * 64})])
def test_contradictory_evidence_replaces_stale_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, mutation: object) -> None:
    directory = fixture(tmp_path)
    verifier(monkeypatch)
    assert main(tmp_path, COMMIT) == 0
    (directory / name).write_text(json.dumps(mutation))
    assert main(tmp_path, COMMIT) == 1
    result = json.loads((directory / "qualification.json").read_text())
    assert result["status"] == "FAIL" and result["alert"] is True


@pytest.mark.parametrize("failure", [OSError("missing gh"), subprocess.TimeoutExpired("gh", 90),
    subprocess.CalledProcessError(1, "gh")])
def test_signature_verification_failure_cannot_use_saved_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception) -> None:
    directory = fixture(tmp_path)
    (directory / "provenance-verification.json").write_text(json.dumps(signature(directory / "image.oci.tar")))
    def rejected(*args: object) -> object:
        raise failure
    monkeypatch.setattr("artifact_gate.verify_signature", rejected)
    assert main(tmp_path, COMMIT) == 1


def test_evidence_write_failure_blocks_completion(tmp_path: Path) -> None:
    destination = tmp_path / "evidence"
    destination.write_text("blocked")
    with pytest.raises(OSError):
        main(tmp_path, COMMIT)
