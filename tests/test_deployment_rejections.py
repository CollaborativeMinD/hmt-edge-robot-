"""Fresh failure receipts supersede old PASS on malformed or absent inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from deployment_admission import evaluate
from deployment_gate import main
from deployment_io import read_object
from deployment_receipts import RejectionReceipt, parse_outcome, verify_receipt
from deployment_support import deployment_copy, rewrite


@pytest.mark.parametrize("contents", ['{', '[]', '{"stage": 3, "stage": 3}', '"' + 'x' * 65536 + '"'])
def test_rejection_replaces_stale_pass_receipt(tmp_path: Path, contents: str) -> None:
    root = deployment_copy(tmp_path)
    expected = evaluate(root)
    assert main(root) == 0
    path = root / "policy/deployment.json"
    path.write_text(contents)
    catalog = json.loads((root / "policy/deployment_admission.json").read_text())
    import hashlib
    catalog["inputs"]["policy/deployment.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    rewrite(root, "policy/deployment_admission.json", catalog)
    assert main(root) == 1
    report = json.loads((root / "evidence/cd/stage3/release_receipt.json").read_text())
    assert report["contract_status"] == "FAIL" and report["release_decision"] == "HOLD"
    assert report["alert"] is True and report["reason_codes"]
    raw = (root / "evidence/cd/stage3/release_receipt.json").read_bytes()
    assert isinstance(parse_outcome(raw), RejectionReceipt)
    import jsonschema
    schema = json.loads((root / "docs/cd/release-receipt.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(report)
    with pytest.raises(ValueError, match="CONTRACT_REJECTED"):
        verify_receipt(expected, raw)


def test_read_object_rejects_nonobject_json(tmp_path: Path) -> None:
    (tmp_path / "object.json").write_text("[]")
    with pytest.raises(ValueError, match="OBJECT_REQUIRED"):
        read_object(tmp_path, "object.json")


def test_rejection_does_not_echo_invalid_credential_values(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = deployment_copy(tmp_path)
    from deployment_support import mutate
    sentinel = "must-not-appear-in-receipt"
    mutate(root, "policy/deployment.json", ("api_secret",), sentinel)
    assert main(root) == 1
    assert sentinel not in capsys.readouterr().out
    assert sentinel not in (root / "evidence/cd/stage3/release_receipt.json").read_text()
