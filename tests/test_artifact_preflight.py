"""Unsigned prerequisite PASS must leave final artifact and deployment on HOLD."""
from __future__ import annotations

import json
from pathlib import Path

from artifact_preflight import main
from artifact_support import COMMIT, fixture


def test_unsigned_prequalification_never_promotes_artifact(tmp_path: Path) -> None:
    fixture(tmp_path)
    assert main(tmp_path, COMMIT) == 0
    report = json.loads((tmp_path / "evidence/cd/stage4/prequalification.json").read_text())
    assert report["status"] == "PASS" and report["qualification"] == "HOLD"
    assert report["signed_provenance"] == "HOLD"
    final = json.loads((tmp_path / "evidence/cd/stage4/qualification.json").read_text())
    assert final["status"] == "HOLD" and final["deployment"] == "HOLD"


def test_failed_prequalification_invalidates_old_final_pass(tmp_path: Path) -> None:
    directory = fixture(tmp_path)
    (directory / "qualification.json").write_text('{"status":"PASS"}')
    (directory / "container.json").write_text('{}')
    assert main(tmp_path, COMMIT) == 1
    assert json.loads((directory / "qualification.json").read_text())["status"] == "FAIL"


def test_signing_policy_hold_cannot_promote_qualified_unsigned_image(tmp_path: Path) -> None:
    from artifact_gate import main as final_gate
    fixture(tmp_path)
    (tmp_path / "policy/artifact_signing.json").write_text('{"backend":"github_native_private_sigstore","status":"HOLD"}')
    assert main(tmp_path, COMMIT) == 0
    assert final_gate(tmp_path, COMMIT) == 1
    report = json.loads((tmp_path / "evidence/cd/stage4/qualification.json").read_text())
    assert report["reason_codes"] == ["SIGNING_BACKEND_NOT_ADMITTED"]
