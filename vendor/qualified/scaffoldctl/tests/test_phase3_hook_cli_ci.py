from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import duckdb
import pytest
import yaml
from phase3_support import git, init_repository
from pydantic import ValidationError

import scaffoldctl.cli as cli
from scaffoldctl.cli import main
from scaffoldctl.exceptions import PhaseThreeError
from scaffoldctl.git_snapshot import GitRepository
from scaffoldctl.hook import execute_pre_commit, execute_tree_validation, install_hook
from scaffoldctl.ledger import DuckDbLedger
from scaffoldctl.phase3_models import HookConfig, SignerProvenance
from scaffoldctl.reason_codes import ReasonCode
from scaffoldctl.semantics import ValidationStatus

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_RESOURCE = PROJECT_ROOT / "src/scaffoldctl/resources/git_perimeter/pre-commit"
WORKFLOW = PROJECT_ROOT / ".github/workflows/scaffoldctl-perimeter.yml"


def _config(root: Path, *, missing_key: bool = False, ledger: Path | None = None) -> HookConfig:
    git_dir = root / ".git"
    private = git_dir / "scaffoldctl/lease-signing-key.pem"
    if missing_key:
        private = git_dir / "scaffoldctl/missing.pem"
    return HookConfig(
        schemaId="urn:scaffoldctl:schema:hook-config:0.3.0",
        schemaVersion="0.3.0",
        repositoryRoot=str(root),
        ledgerPath=str(ledger or git_dir / "scaffoldctl/evidence.duckdb"),
        privateKeyPath=str(private),
        baselineTree="HEAD",
        leaseTtlSeconds=300,
        signerProvenance=SignerProvenance.LOCAL_REPOSITORY_KEY,
    )


def test_install_hook_creates_exact_wrapper_and_key_without_overwrite(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    first = install_hook(str(root))
    hook_path = root / ".git/hooks/pre-commit"
    key_path = root / ".git/scaffoldctl/lease-signing-key.pem"
    assert first.hookCreated is True
    assert first.keyCreated is True
    assert hook_path.read_bytes() == HOOK_RESOURCE.read_bytes()
    assert stat.S_IMODE(hook_path.stat().st_mode) == 0o755
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    second = install_hook(str(root))
    assert second.hookCreated is False
    assert second.keyCreated is False
    hook_path.write_text("#!/bin/sh\nexit 0\n")
    before = key_path.read_bytes()
    with pytest.raises(PhaseThreeError) as raised:
        install_hook(str(root))
    assert raised.value.reason_code is ReasonCode.HOOK_INSTALL_CONFLICT
    assert key_path.read_bytes() == before


def test_pre_commit_pass_persists_validation_and_signed_lease(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    install_hook(str(root))
    receipt = execute_pre_commit(_config(root))
    assert receipt.exitCode == 0
    assert receipt.assetLease is not None
    assert receipt.ledgerAppendReceipt is not None
    assert receipt.validationStatus is ValidationStatus.PASS
    verified = DuckDbLedger(root / ".git/scaffoldctl/evidence.duckdb").verify()
    assert verified.validationReceiptCount == 1
    assert verified.assetLeaseCount == 1


def test_pre_commit_missing_file_is_exit_one_and_persisted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    install_hook(str(root))
    root.joinpath("README.md").unlink()
    git(root, "add", "--all")
    receipt = execute_pre_commit(_config(root))
    assert receipt.exitCode == 1
    assert receipt.assetLease is None
    assert ReasonCode.DOCUMENT_MISSING in receipt.validationReceipt.boundaries[0].reasonCodes
    verified = DuckDbLedger(root / ".git/scaffoldctl/evidence.duckdb").verify()
    assert verified.validationReceiptCount == 1
    assert verified.assetLeaseCount == 0


def test_pre_commit_missing_key_and_ledger_failure_reject(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    missing = execute_pre_commit(_config(root, missing_key=True))
    assert missing.exitCode == 1
    assert ReasonCode.LEASE_KEY_MISSING in missing.validationReceipt.reasonCodes
    install_hook(str(root))
    bad_parent = tmp_path / "not-directory"
    bad_parent.write_text("occupied")
    failed = execute_pre_commit(_config(root, ledger=bad_parent / "ledger.duckdb"))
    assert failed.exitCode == 1
    assert failed.ledgerAppendReceipt is not None
    assert failed.ledgerAppendReceipt.transactionCommitted is False
    assert ReasonCode.LEDGER_APPEND_FAILED in failed.reasonCodes


def test_tree_validation_uses_commit_objects_and_baseline(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    install_hook(str(root))
    receipt = execute_tree_validation(
        root=str(root),
        treeish="HEAD",
        baseline_treeish=None,
        ledger_path=str(root / ".git/scaffoldctl/tree.duckdb"),
        private_key_path=str(root / ".git/scaffoldctl/lease-signing-key.pem"),
        provenance=SignerProvenance.CI_EPHEMERAL_KEY,
    )
    assert receipt.exitCode == 0
    assert receipt.assetLease is not None
    assert receipt.assetLease.signerProvenance is SignerProvenance.CI_EPHEMERAL_KEY
    assert receipt.validationReceipt.sourceRef == GitRepository(root).resolve_tree("HEAD")


def test_native_wrapper_maps_every_nonzero_status_to_one(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    fake = tmp_path / "fake-scaffoldctl"
    fake.write_text("#!/bin/sh\nexit 27\n")
    fake.chmod(0o755)
    environment = {**os.environ, "SCAFFOLDCTL_BIN": str(fake)}
    rejected = subprocess.run(
        ("sh", str(HOOK_RESOURCE)),
        cwd=root,
        check=False,
        capture_output=True,
        env=environment,
    )
    assert rejected.returncode == 1
    fake.write_text("#!/bin/sh\nexit 0\n")
    admitted = subprocess.run(
        ("sh", str(HOOK_RESOURCE)),
        cwd=root,
        check=False,
        capture_output=True,
        env=environment,
    )
    assert admitted.returncode == 0


def test_cli_phase_three_happy_path_and_sealing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    assert main(["install-hook", "--root", str(root)]) == 0
    capsys.readouterr()
    assert main(["pre-commit", "--root", str(root)]) == 0
    hook = json.loads(capsys.readouterr().out)
    assert hook["exitCode"] == 0
    ledger = root / ".git/scaffoldctl/evidence.duckdb"
    key = root / ".git/scaffoldctl/lease-signing-key.pem"
    assert main(["verify-ledger", "--ledger", str(ledger)]) == 0
    assert json.loads(capsys.readouterr().out)["recordCount"] == 2
    output = tmp_path / "seal.json"
    assert (
        main(
            [
                "seal-ledger",
                "--ledger",
                str(ledger),
                "--private-key",
                str(key),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    seal = json.loads(capsys.readouterr().out)
    assert seal == json.loads(output.read_text())
    assert main(["verify-ledger", "--ledger", str(ledger)]) == 0
    assert json.loads(capsys.readouterr().out)["ledgerSealCount"] == 1


def test_cli_staged_and_tree_rejections_are_explicit_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    assert main(["install-hook", "--root", str(root)]) == 0
    capsys.readouterr()
    root.joinpath("Start_here.md").unlink()
    git(root, "add", "--all")
    assert main(["validate", "--staged", "--root", str(root)]) == 1
    assert json.loads(capsys.readouterr().out)["exitCode"] == 1
    git(root, "commit", "--quiet", "--no-verify", "-m", "invalid")
    assert main(["validate", "--tree", "HEAD", "--root", str(root)]) == 1
    assert json.loads(capsys.readouterr().out)["exitCode"] == 1


def test_cli_keygen_and_schema_are_strict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    assert (
        main(
            [
                "keygen",
                "--private-key",
                str(private),
                "--public-key",
                str(public),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["created"] is True
    assert main(["schema", "hook-config"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["additionalProperties"] is False
    with pytest.raises(ValidationError):
        HookConfig.model_validate(
            {
                **_config(tmp_path).model_dump(mode="python"),
                "leaseTtlSeconds": "300",
            }
        )


def test_cli_errors_are_reason_coded_and_fail_closed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(["verify-ledger", "--ledger", str(tmp_path / "missing.duckdb")]) == 1
    assert json.loads(capsys.readouterr().out)["exitCode"] == 1

    def reject(_root: str) -> object:
        raise PhaseThreeError(ReasonCode.HOOK_INSTALL_CONFLICT, "conflict", exit_code=1)

    monkeypatch.setattr(cli, "install_hook", reject)
    assert main(["install-hook", "--root", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["reasonCodes"] == [
        ReasonCode.HOOK_INSTALL_CONFLICT.value
    ]


def test_workflow_is_valid_pinned_and_fail_closed() -> None:
    payload = yaml.safe_load(WORKFLOW.read_text())
    assert payload["permissions"] == {"contents": "read"}
    job = payload["jobs"]["validate-tree"]
    assert job["timeout-minutes"] == 10
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert uses == [
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9",
        "actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f",
    ]
    text = WORKFLOW.read_text()
    assert "persist-credentials: false" in text
    assert "8462f8af16f6a5612572a35c8ec6615de9235198d3116bdf5ce623f48e249159" in text
    assert "__PHASE3_WHEEL_SHA256__" not in text
    assert "scaffoldctl validate --tree" in text
    assert "scaffoldctl seal-ledger" in text
    assert 'test "$PERIMETER_STATUS" = 0' in text
    assert 'test "$SEAL_STATUS" = 0' in text


def test_packaged_wrapper_starts_with_shebang_and_fails_closed() -> None:
    assert HOOK_RESOURCE.read_bytes().startswith(b"#!/bin/sh\n")
    assert b"exit 1\n" in HOOK_RESOURCE.read_bytes()


def test_duckdb_validation_and_lease_rows_are_native_columns(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    init_repository(root)
    install_hook(str(root))
    execute_pre_commit(_config(root))
    connection = duckdb.connect(str(root / ".git/scaffoldctl/evidence.duckdb"), read_only=True)
    try:
        validation = connection.execute(
            "SELECT validation_status, exit_code, source_kind FROM validation_receipts"
        ).fetchone()
        lease = connection.execute("SELECT purpose, key_id FROM asset_leases").fetchone()
    finally:
        connection.close()
    assert validation == ("pass", 0, "git_index")
    assert lease is not None and lease[0] == "pre_commit" and len(lease[1]) == 64
