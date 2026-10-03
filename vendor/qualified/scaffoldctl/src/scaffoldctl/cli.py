from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from scaffoldctl.authority import (
    PHASE_0_BASELINE,
    PHASE_2_BUILD_AUTHORITY,
    PHASE_3_BUILD_AUTHORITY,
)
from scaffoldctl.engine import ScaffoldEngine, failure_receipt, load_plan, load_receipt
from scaffoldctl.exceptions import PhaseTwoError
from scaffoldctl.git_snapshot import GitRepository
from scaffoldctl.hook import (
    execute_pre_commit,
    execute_tree_validation,
    install_hook,
    keygen_receipt,
)
from scaffoldctl.integrity import canonical_json_bytes
from scaffoldctl.lease import load_private_key
from scaffoldctl.ledger import DuckDbLedger
from scaffoldctl.lifecycle import STATE_DEFINITIONS, TRANSITION_RULES
from scaffoldctl.models import (
    ContractValidationReceipt,
    LifecycleTransition,
    RepositoryRootDirectory,
)
from scaffoldctl.ontology import OntologyAuthorityError, verify_ontology_authority
from scaffoldctl.phase2_models import (
    BoundaryPolicy,
    BoundarySpec,
    OperationName,
    OperationReceipt,
    ScaffoldPlan,
)
from scaffoldctl.phase3_models import (
    AssetLease,
    GitObjectMatrix,
    HookConfig,
    HookExecutionReceipt,
    LedgerAppendReceipt,
    LedgerSeal,
    LedgerVerificationReceipt,
    PerimeterValidationReceipt,
    SignerProvenance,
)
from scaffoldctl.policy import verify_phase_two_resource_authority
from scaffoldctl.reason_codes import ReasonCode


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _emit(value: Any) -> None:
    print(
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _add_phase_three_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".")
    parser.add_argument("--ledger")
    parser.add_argument("--private-key")
    parser.add_argument("--lease-ttl", type=int, default=300)
    parser.add_argument(
        "--signer-provenance",
        choices=tuple(item.value for item in SignerProvenance),
        default=SignerProvenance.LOCAL_REPOSITORY_KEY.value,
    )


def _add_contract_commands(commands: argparse._SubParsersAction[Any]) -> None:
    commands.add_parser("authority")
    commands.add_parser("state-table")
    schema = commands.add_parser("schema")
    schema.add_argument(
        "model",
        choices=(
            "hmt-root",
            "lifecycle-transition",
            "boundary-policy",
            "scaffold-plan",
            "operation-receipt",
            "git-object-matrix",
            "perimeter-validation-receipt",
            "asset-lease",
            "ledger-append-receipt",
            "ledger-verification-receipt",
            "ledger-seal",
            "hook-config",
            "hook-execution-receipt",
        ),
    )
    validate_root = commands.add_parser("validate-root")
    validate_root.add_argument("input", help="strict JSON payload path or '-' for stdin")


def _add_scaffolding_commands(commands: argparse._SubParsersAction[Any]) -> None:
    plan = commands.add_parser("plan")
    plan.add_argument("--root", default=".")
    plan.add_argument("--target", default=".")
    plan.add_argument("--boundary-id", required=True)
    plan.add_argument("--title", required=True)
    plan.add_argument("--purpose", required=True)
    scaffold = commands.add_parser("scaffold")
    scaffold.add_argument("input", help="strict scaffold-plan JSON path or '-' for stdin")
    scaffold.add_argument("--root", default=".")
    validate = commands.add_parser("validate")
    mode = validate.add_mutually_exclusive_group(required=True)
    mode.add_argument("--worktree", action="store_true")
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--tree")
    _add_phase_three_paths(validate)
    validate.add_argument("--target", default=".")
    validate.add_argument("--baseline-tree")
    audit = commands.add_parser("audit")
    audit.add_argument("--worktree", action="store_true", required=True)
    audit.add_argument("--root", default=".")
    audit.add_argument("--target", default=".")
    audit.add_argument("--receipt")


def _add_evidence_commands(commands: argparse._SubParsersAction[Any]) -> None:
    pre_commit = commands.add_parser("pre-commit")
    _add_phase_three_paths(pre_commit)
    pre_commit.add_argument("--baseline-tree", default="HEAD")
    keygen = commands.add_parser("keygen")
    keygen.add_argument("--private-key", required=True)
    keygen.add_argument("--public-key", required=True)
    install = commands.add_parser("install-hook")
    install.add_argument("--root", default=".")
    verify_ledger = commands.add_parser("verify-ledger")
    verify_ledger.add_argument("--ledger", required=True)
    seal = commands.add_parser("seal-ledger")
    seal.add_argument("--ledger", required=True)
    seal.add_argument("--private-key", required=True)
    seal.add_argument(
        "--signer-provenance",
        choices=tuple(item.value for item in SignerProvenance),
        default=SignerProvenance.RELEASE_KEY.value,
    )
    seal.add_argument("--output")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scaffoldctl")
    commands = parser.add_subparsers(dest="command", required=True)
    _add_contract_commands(commands)
    _add_scaffolding_commands(commands)
    _add_evidence_commands(commands)
    return parser


def _authority() -> int:
    try:
        receipt = verify_ontology_authority()
        phase_two_receipt = verify_phase_two_resource_authority()
    except (OntologyAuthorityError, PhaseTwoError) as exc:
        _emit({"reasonCodes": [exc.reason_code.value], "validationStatus": "fail"})
        return 2
    _emit(
        {
            "phaseZeroBaseline": PHASE_0_BASELINE.model_dump(mode="json"),
            "phaseTwoBuildAuthority": PHASE_2_BUILD_AUTHORITY.model_dump(mode="json"),
            "phaseTwoResourceAuthorityReceipt": phase_two_receipt.model_dump(mode="json"),
            "phaseThreeBuildAuthority": PHASE_3_BUILD_AUTHORITY.model_dump(mode="json"),
            "semanticAuthorityReceipt": receipt.model_dump(mode="json"),
        }
    )
    return 0


def _state_table() -> int:
    _emit(
        {
            "states": [state.name for state in STATE_DEFINITIONS],
            "transitions": [
                {
                    "reopening": rule.reopening,
                    "source": rule.source.value,
                    "target": rule.target.value,
                    "trigger": rule.trigger.value,
                    "validatesAgainstMinimum": 1,
                }
                for rule in TRANSITION_RULES
            ],
        }
    )
    return 0


def _schema(model: str) -> int:
    contracts = {
        "asset-lease": AssetLease,
        "boundary-policy": BoundaryPolicy,
        "git-object-matrix": GitObjectMatrix,
        "hmt-root": RepositoryRootDirectory,
        "hook-config": HookConfig,
        "hook-execution-receipt": HookExecutionReceipt,
        "ledger-append-receipt": LedgerAppendReceipt,
        "ledger-seal": LedgerSeal,
        "ledger-verification-receipt": LedgerVerificationReceipt,
        "lifecycle-transition": LifecycleTransition,
        "operation-receipt": OperationReceipt,
        "perimeter-validation-receipt": PerimeterValidationReceipt,
        "scaffold-plan": ScaffoldPlan,
    }
    _emit(contracts[model].model_json_schema())
    return 0


def _read_payload(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _validation_error(payload: bytes, errors: tuple[str, ...]) -> ContractValidationReceipt:
    return ContractValidationReceipt(
        validationStatus="fail",
        reasonCodes=(ReasonCode.SCHEMA_INVALID.value,),
        modelName=RepositoryRootDirectory.__name__,
        payloadSha256=hashlib.sha256(payload).hexdigest(),
        errorCount=len(errors),
        errors=errors,
    )


def _validate_root(path: str) -> int:
    try:
        payload = _read_payload(path)
    except OSError as exc:
        encoded = str(exc).encode("utf-8")
        _emit(_validation_error(encoded, (type(exc).__name__,)))
        return 2
    try:
        RepositoryRootDirectory.model_validate_json(payload)
    except ValidationError as exc:
        errors = tuple(
            f"{'.'.join(str(item) for item in error['loc'])}:{error['type']}"
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        )
        _emit(_validation_error(payload, errors))
        return 1
    _emit(
        ContractValidationReceipt(
            validationStatus="pass",
            reasonCodes=(ReasonCode.TRIFECTA_VALID.value, ReasonCode.SCHEMA_VALID.value),
            modelName=RepositoryRootDirectory.__name__,
            payloadSha256=hashlib.sha256(payload).hexdigest(),
            errorCount=0,
            errors=(),
        )
    )
    return 0


def _phase_two_error(error: BaseException, default_reason: ReasonCode) -> PhaseTwoError:
    if isinstance(error, PhaseTwoError):
        return error
    return PhaseTwoError(default_reason, "strict Phase 2 boundary rejected input")


def _plan(arguments: argparse.Namespace) -> int:
    try:
        boundary = BoundarySpec(
            boundaryId=arguments.boundary_id,
            targetPath=arguments.target,
            title=arguments.title,
            purpose=arguments.purpose,
        )
        plan = ScaffoldEngine(arguments.root).plan(boundary)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        receipt = failure_receipt(
            OperationName.PLAN,
            arguments.target,
            _phase_two_error(exc, ReasonCode.PLAN_INVALID),
        )
        _emit(receipt)
        return receipt.exitCode
    _emit(plan)
    return 0


def _scaffold(arguments: argparse.Namespace) -> int:
    target = "."
    try:
        plan = load_plan(_read_payload(arguments.input))
        target = plan.boundary.targetPath
        receipt = ScaffoldEngine(arguments.root).scaffold(plan)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        receipt = failure_receipt(
            OperationName.SCAFFOLD,
            target,
            _phase_two_error(exc, ReasonCode.PLAN_INVALID),
        )
    _emit(receipt)
    return receipt.exitCode


def _validate_worktree(arguments: argparse.Namespace) -> int:
    try:
        receipt = ScaffoldEngine(arguments.root).validate_worktree(arguments.target)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        receipt = failure_receipt(
            OperationName.VALIDATE_WORKTREE,
            arguments.target,
            _phase_two_error(exc, ReasonCode.WORKTREE_INVALID),
        )
    _emit(receipt)
    return receipt.exitCode


def _audit_worktree(arguments: argparse.Namespace) -> int:
    try:
        replay = load_receipt(_read_payload(arguments.receipt)) if arguments.receipt else None
        receipt = ScaffoldEngine(arguments.root).audit_worktree(arguments.target, replay)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        receipt = failure_receipt(
            OperationName.AUDIT_WORKTREE,
            arguments.target,
            _phase_two_error(exc, ReasonCode.WORKTREE_INVALID),
        )
    _emit(receipt)
    return receipt.exitCode


def _phase_three_locations(arguments: argparse.Namespace) -> tuple[str, str]:
    repository = GitRepository(arguments.root)
    ledger = arguments.ledger or os.fspath(repository.git_dir / "scaffoldctl" / "evidence.duckdb")
    private_key = arguments.private_key or os.fspath(
        repository.git_dir / "scaffoldctl" / "lease-signing-key.pem"
    )
    return ledger, private_key


def _hook_config(arguments: argparse.Namespace, baseline: str | None) -> HookConfig:
    ledger, private_key = _phase_three_locations(arguments)
    return HookConfig(
        schemaId="urn:scaffoldctl:schema:hook-config:0.3.0",
        schemaVersion="0.3.0",
        repositoryRoot=arguments.root,
        ledgerPath=ledger,
        privateKeyPath=private_key,
        baselineTree=baseline,
        leaseTtlSeconds=arguments.lease_ttl,
        signerProvenance=SignerProvenance(arguments.signer_provenance),
    )


def _validate_phase_three(arguments: argparse.Namespace) -> int:
    try:
        if arguments.staged:
            receipt = execute_pre_commit(_hook_config(arguments, arguments.baseline_tree or "HEAD"))
        else:
            ledger, private_key = _phase_three_locations(arguments)
            receipt = execute_tree_validation(
                root=arguments.root,
                treeish=arguments.tree,
                baseline_treeish=arguments.baseline_tree,
                ledger_path=ledger,
                private_key_path=private_key,
                provenance=SignerProvenance(arguments.signer_provenance),
                lease_ttl_seconds=arguments.lease_ttl,
            )
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(receipt)
    return receipt.exitCode


def _pre_commit(arguments: argparse.Namespace) -> int:
    try:
        receipt = execute_pre_commit(_hook_config(arguments, arguments.baseline_tree))
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(receipt)
    return receipt.exitCode


def _phase_three_error(error: BaseException) -> int:
    reason = error.reason_code if isinstance(error, PhaseTwoError) else ReasonCode.INTERNAL_ERROR
    _emit({"exitCode": 1, "reasonCodes": [reason.value], "validationStatus": "fail"})
    return 1


def _keygen(arguments: argparse.Namespace) -> int:
    try:
        receipt = keygen_receipt(arguments.private_key, arguments.public_key)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(receipt)
    return 0


def _install_hook(arguments: argparse.Namespace) -> int:
    try:
        receipt = install_hook(arguments.root)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(receipt)
    return 0


def _verify_ledger(arguments: argparse.Namespace) -> int:
    try:
        receipt = DuckDbLedger(arguments.ledger).verify()
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(receipt)
    return 0


def _exclusive_output(path: str, model: BaseModel) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    absolute = Path(os.path.abspath(path))
    absolute.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(absolute, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(canonical_json_bytes(model) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _seal_ledger(arguments: argparse.Namespace) -> int:
    try:
        key = load_private_key(arguments.private_key)
        seal = DuckDbLedger(arguments.ledger).seal(
            key,
            SignerProvenance(arguments.signer_provenance),
        )
        if arguments.output:
            _exclusive_output(arguments.output, seal)
    except (PhaseTwoError, ValidationError, OSError, ValueError) as exc:
        return _phase_three_error(exc)
    _emit(seal)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "authority":
        return _authority()
    if arguments.command == "state-table":
        return _state_table()
    if arguments.command == "schema":
        return _schema(arguments.model)
    if arguments.command == "validate-root":
        return _validate_root(arguments.input)
    if arguments.command == "plan":
        return _plan(arguments)
    if arguments.command == "scaffold":
        return _scaffold(arguments)
    if arguments.command == "validate":
        return (
            _validate_worktree(arguments)
            if arguments.worktree
            else _validate_phase_three(arguments)
        )
    if arguments.command == "audit":
        return _audit_worktree(arguments)
    if arguments.command == "pre-commit":
        return _pre_commit(arguments)
    if arguments.command == "keygen":
        return _keygen(arguments)
    if arguments.command == "install-hook":
        return _install_hook(arguments)
    if arguments.command == "verify-ledger":
        return _verify_ledger(arguments)
    if arguments.command == "seal-ledger":
        return _seal_ledger(arguments)
    raise AssertionError(f"unhandled command: {arguments.command}")  # pragma: no cover
