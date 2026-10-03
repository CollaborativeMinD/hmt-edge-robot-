import json
from io import BytesIO, TextIOWrapper

import pytest

import scaffoldctl.cli as cli
from scaffoldctl.cli import main
from scaffoldctl.ontology import OntologyAuthorityError
from scaffoldctl.reason_codes import ReasonCode


def _root_payload(line_count: int) -> dict[str, object]:
    return {
        "hasHMTTrifectaDocument": [
            {"canonicalRelativePath": "README.md", "lineCount": line_count},
            {"canonicalRelativePath": "Start_here.md", "lineCount": line_count},
            {"canonicalRelativePath": "Index.md", "lineCount": line_count},
        ]
    }


def test_authority_command(capsys: object) -> None:
    assert main(["authority"]) == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["semanticAuthorityReceipt"]["validationStatus"] == "pass"


def test_state_table_command(capsys: object) -> None:
    assert main(["state-table"]) == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["states"][0] == "Uninitialized"
    assert output["states"][-1] == "Rejected"


def test_schema_commands(capsys: object) -> None:
    assert main(["schema", "hmt-root"]) == 0
    root_schema = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert root_schema["additionalProperties"] is False
    assert main(["schema", "lifecycle-transition"]) == 0
    transition_schema = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert transition_schema["additionalProperties"] is False


def test_validate_root_command_pass_and_fail(tmp_path: object, capsys: object) -> None:
    valid = tmp_path / "valid.json"  # type: ignore[operator]
    valid.write_text(json.dumps(_root_payload(99)), encoding="utf-8")
    assert main(["validate-root", str(valid)]) == 0
    passed = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert passed["validationStatus"] == "pass"
    invalid = tmp_path / "invalid.json"  # type: ignore[operator]
    invalid.write_text(json.dumps(_root_payload(100)), encoding="utf-8")
    assert main(["validate-root", str(invalid)]) == 1
    failed = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert failed["validationStatus"] == "fail"
    assert failed["errorCount"] >= 1


def test_validate_root_reads_stdin(monkeypatch: pytest.MonkeyPatch, capsys: object) -> None:
    stream = TextIOWrapper(BytesIO(json.dumps(_root_payload(1)).encode("utf-8")))
    monkeypatch.setattr(cli.sys, "stdin", stream)
    assert main(["validate-root", "-"]) == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["validationStatus"] == "pass"


def test_validate_root_missing_file_is_fail_closed(tmp_path: object, capsys: object) -> None:
    missing = tmp_path / "missing.json"  # type: ignore[operator]
    assert main(["validate-root", str(missing)]) == 2
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output["validationStatus"] == "fail"
    assert output["errors"] == ["FileNotFoundError"]


def test_authority_command_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: object,
) -> None:
    def fail() -> None:
        raise OntologyAuthorityError(ReasonCode.ONTOLOGY_HASH_MISMATCH, "tampered")

    monkeypatch.setattr(cli, "verify_ontology_authority", fail)
    assert main(["authority"]) == 2
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output == {
        "reasonCodes": [ReasonCode.ONTOLOGY_HASH_MISMATCH.value],
        "validationStatus": "fail",
    }
