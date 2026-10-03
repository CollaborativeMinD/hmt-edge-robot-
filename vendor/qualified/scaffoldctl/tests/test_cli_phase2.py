import json
from io import BytesIO, TextIOWrapper
from pathlib import Path

import pytest

import scaffoldctl.cli as cli
from scaffoldctl.cli import main
from scaffoldctl.engine import load_plan, load_receipt
from scaffoldctl.integrity import canonical_json_bytes
from scaffoldctl.reason_codes import ReasonCode


def _plan_arguments(root: Path, target: str = "systems/demo") -> list[str]:
    return [
        "plan",
        "--root",
        str(root),
        "--target",
        target,
        "--boundary-id",
        "systems.demo",
        "--title",
        "Demo Boundary",
        "--purpose",
        "Exercise the bounded CLI.",
    ]


def _capture_json(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)


def test_authority_includes_phase_two_pins(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["authority"]) == 0
    output = _capture_json(capsys)
    assert output["phaseTwoBuildAuthority"]["validationStatus"] == "pass"  # type: ignore[index]
    assert output["phaseTwoResourceAuthorityReceipt"]["validationStatus"] == "pass"  # type: ignore[index]


@pytest.mark.parametrize(
    "model",
    ["boundary-policy", "scaffold-plan", "operation-receipt"],
)
def test_phase_two_schema_commands(
    model: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["schema", model]) == 0
    output = _capture_json(capsys)
    assert output["additionalProperties"] is False


def test_cli_plan_scaffold_validate_and_audit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_plan_arguments(tmp_path)) == 0
    plan_payload = _capture_json(capsys)
    plan = load_plan(canonical_json_bytes(plan_payload))
    plan_file = tmp_path / "plan.json"
    plan_file.write_bytes(canonical_json_bytes(plan))
    assert main(["scaffold", str(plan_file), "--root", str(tmp_path)]) == 0
    scaffold_payload = _capture_json(capsys)
    scaffold = load_receipt(canonical_json_bytes(scaffold_payload))
    receipt_file = tmp_path / "receipt.json"
    receipt_file.write_bytes(canonical_json_bytes(scaffold))
    assert (
        main(
            [
                "validate",
                "--worktree",
                "--root",
                str(tmp_path),
                "--target",
                "systems/demo",
            ]
        )
        == 0
    )
    validation = _capture_json(capsys)
    assert validation["validationStatus"] == "pass"
    assert (
        main(
            [
                "audit",
                "--worktree",
                "--root",
                str(tmp_path),
                "--target",
                "systems/demo",
                "--receipt",
                str(receipt_file),
            ]
        )
        == 0
    )
    audit = _capture_json(capsys)
    assert ReasonCode.RECEIPT_VERIFIED.value in audit["reasonCodes"]


def test_scaffold_reads_plan_from_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(_plan_arguments(tmp_path, ".")) == 0
    plan_payload = _capture_json(capsys)
    stream = TextIOWrapper(BytesIO(canonical_json_bytes(plan_payload)))
    monkeypatch.setattr(cli.sys, "stdin", stream)
    assert main(["scaffold", "-", "--root", str(tmp_path)]) == 0
    output = _capture_json(capsys)
    assert output["validationStatus"] == "pass"


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "plan",
            "--target",
            "../escape",
            "--boundary-id",
            "demo",
            "--title",
            "Demo",
            "--purpose",
            "Purpose.",
        ],
        [
            "plan",
            "--target",
            ".",
            "--boundary-id",
            "Upper",
            "--title",
            "Demo",
            "--purpose",
            "Purpose.",
        ],
    ],
)
def test_cli_plan_invalid_input_is_structured_failure(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(arguments) == 2
    output = _capture_json(capsys)
    assert output["operation"] == "plan"
    assert output["validationStatus"] == "fail"
    assert output["reasonCodes"] == [ReasonCode.PLAN_INVALID.value]


def test_cli_plan_invalid_root_is_structured_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"
    assert main([*_plan_arguments(missing, ".")]) == 2
    output = _capture_json(capsys)
    assert output["reasonCodes"] == [ReasonCode.ROOT_INVALID.value]


def test_cli_scaffold_rejects_missing_and_tampered_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.json"
    assert main(["scaffold", str(missing), "--root", str(tmp_path)]) == 2
    output = _capture_json(capsys)
    assert output["reasonCodes"] == [ReasonCode.PLAN_INVALID.value]
    assert main(_plan_arguments(tmp_path)) == 0
    plan = _capture_json(capsys)
    plan["planHash"] = "0" * 64
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["scaffold", str(tampered), "--root", str(tmp_path)]) == 2
    output = _capture_json(capsys)
    assert output["reasonCodes"] == [ReasonCode.PLAN_INVALID.value]


def test_cli_validate_and_audit_fail_closed_on_missing_boundary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = ["--worktree", "--root", str(tmp_path), "--target", "missing"]
    assert main(["validate", *arguments]) == 1
    validation = _capture_json(capsys)
    assert ReasonCode.TARGET_MISSING.value in validation["reasonCodes"]
    assert main(["audit", *arguments]) == 1
    audit = _capture_json(capsys)
    assert ReasonCode.AUDIT_COMPLETE.value in audit["reasonCodes"]


def test_cli_validate_invalid_target_is_structured_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [
        "validate",
        "--worktree",
        "--root",
        str(tmp_path),
        "--target",
        "../escape",
    ]
    assert main(arguments) == 2
    output = _capture_json(capsys)
    assert output["reasonCodes"] == [ReasonCode.PATH_TRAVERSAL.value]


def test_cli_audit_rejects_tampered_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    arguments = [
        "audit",
        "--worktree",
        "--root",
        str(tmp_path),
        "--target",
        ".",
        "--receipt",
        str(receipt),
    ]
    assert main(arguments) == 2
    output = _capture_json(capsys)
    assert output["reasonCodes"] == [ReasonCode.RECEIPT_HASH_INVALID.value]
