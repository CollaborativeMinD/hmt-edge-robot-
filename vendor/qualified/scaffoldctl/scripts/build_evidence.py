from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import scaffoldctl.perimeter as perimeter_module
from scaffoldctl.authority import (
    PHASE_0_BASELINE,
    PHASE_2_BUILD_AUTHORITY,
    PHASE_3_BUILD_AUTHORITY,
    MachineHandoffBody,
    MachineHandoffResponse,
)
from scaffoldctl.git_snapshot import GitRepository
from scaffoldctl.integrity import canonical_json_bytes, hash_payload, parse_strict_json
from scaffoldctl.lease import sign_asset_lease
from scaffoldctl.ledger import DuckDbLedger
from scaffoldctl.lifecycle import LifecycleController
from scaffoldctl.models import CriterionEvidence, TransitionRequest
from scaffoldctl.ontology import verify_ontology_authority
from scaffoldctl.phase2_models import BoundarySpec
from scaffoldctl.phase3_models import LeasePurpose, SignerProvenance
from scaffoldctl.policy import render_boundary, verify_phase_two_resource_authority
from scaffoldctl.semantics import (
    ONTOLOGY_SHA256,
    PACKAGE_VERSION,
    PHASE_THREE_SUBMITTED_TOKEN,
    PHASE_THREE_UPSTREAM_ARCHIVE_SHA256,
    PHASE_THREE_UPSTREAM_WHEEL_SHA256,
    PHASE_TWO_POLICY_PACK_SHA256,
    PHASE_TWO_TEMPLATE_PACK_SHA256,
    LifecycleState,
    LifecycleTrigger,
    ValidationStatus,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
DIST = ROOT / "dist"
RELEASE_TIME = datetime(2026, 8, 3, tzinfo=UTC)
RELEASE_TIMESTAMP = "2026-08-03T00:00:00.000000Z"
SOURCE_DATE_EPOCH = "1785715200"
PROVENANCE_ID = "prov_semantic_scaffolding_phase_3_20260803_v0_3_0"
WHEEL_NAME = f"scaffoldctl-{PACKAGE_VERSION}-py3-none-any.whl"
SDIST_NAME = f"scaffoldctl-{PACKAGE_VERSION}.tar.gz"
EXCLUDED_PARTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-archive", type=Path, required=True)
    parser.add_argument("--minimum-coverage", type=float, default=95.0)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_bytes(path, canonical_json_bytes(value) + b"\n")


def _command(
    arguments: list[str],
    *,
    environment: dict[str, str],
    cwd: Path = ROOT,
) -> str:
    completed = subprocess.run(
        arguments,
        check=False,
        cwd=cwd,
        env=environment,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        diagnostic = completed.stdout[-6000:]
        raise RuntimeError(
            f"gate failed ({completed.returncode}): {' '.join(arguments)}\n{diagnostic}"
        )
    return completed.stdout


def _tool(name: str) -> str:
    local = Path(sys.executable).with_name(name)
    discovered = shutil.which(name)
    if local.is_file():
        return os.fspath(local)
    if discovered is not None:
        return discovered
    raise FileNotFoundError(f"required tool unavailable: {name}")


def _upstream_files(path: Path) -> dict[str, bytes]:
    if _sha256(path) != PHASE_THREE_UPSTREAM_ARCHIVE_SHA256:
        raise RuntimeError("Phase 2 archive hash mismatch")
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        members = tuple(item for item in archive.infolist() if not item.is_dir())
        roots = {PurePosixPath(item.filename).parts[0] for item in members}
        if len(roots) != 1:
            raise RuntimeError("Phase 2 archive must have one root")
        archive_root = next(iter(roots))
        for member in members:
            archive_path = PurePosixPath(member.filename)
            if (
                archive_path.is_absolute()
                or ".." in archive_path.parts
                or archive_path.parts[0] != archive_root
            ):
                raise RuntimeError("Phase 2 archive path is unsafe")
            relative = PurePosixPath(*archive_path.parts[1:]).as_posix()
            if not relative or relative in files:
                raise RuntimeError("Phase 2 archive path is duplicate")
            files[relative] = archive.read(member)
    wheel = files.get("dist/scaffoldctl-0.2.0-py3-none-any.whl")
    if wheel is None or _sha256_bytes(wheel) != PHASE_THREE_UPSTREAM_WHEEL_SHA256:
        raise RuntimeError("Phase 2 wheel hash mismatch")
    return files


def _clean_outputs() -> None:
    for directory in (EVIDENCE, DIST):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(mode=0o700)


def _coverage(path: Path, minimum: float) -> dict[str, Any]:
    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    percent = round(float(totals["percent_covered"]), 2)
    if percent < minimum:
        raise RuntimeError("branch-aware coverage gate failed")
    return {
        "branchAware": True,
        "branchesCovered": totals["covered_branches"],
        "branchesTotal": totals["num_branches"],
        "linesCovered": totals["covered_lines"],
        "linesTotal": totals["num_statements"],
        "minimumPercent": minimum,
        "observedPercent": percent,
        "status": "pass",
    }


def _test_count(output: str) -> int:
    match = re.search(r"(?m)(\d+) passed(?:, [^\n]+)? in [0-9.]+s", output)
    if match is None:
        raise RuntimeError("pytest count could not be derived")
    return int(match.group(1))


def _build_twice(uv: str, environment: dict[str, str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="scaffoldctl-phase3-build-") as temporary:
        base = Path(temporary)
        hashes: list[dict[str, str]] = []
        for name in ("first", "second"):
            output = base / name
            _command(
                [uv, "build", "--clear", "--offline", "--out-dir", os.fspath(output)],
                environment=environment,
            )
            hashes.append(
                {
                    WHEEL_NAME: _sha256(output / WHEEL_NAME),
                    SDIST_NAME: _sha256(output / SDIST_NAME),
                }
            )
        if hashes[0] != hashes[1]:
            raise RuntimeError("wheel or sdist is not reproducible")
        for name in (WHEEL_NAME, SDIST_NAME):
            shutil.copyfile(base / "first" / name, DIST / name)
    workflow = (ROOT / ".github/workflows/scaffoldctl-perimeter.yml").read_text()
    if hashes[0][WHEEL_NAME] not in workflow or "__PHASE3_WHEEL_SHA256__" in workflow:
        raise RuntimeError("CI wheel pin does not match the built wheel")
    return {
        "buildBackend": "uv_build",
        "distributions": hashes[0],
        "sourceDateEpoch": int(SOURCE_DATE_EPOCH),
        "status": "pass",
    }


def _upstream_wheel_smoke(
    uv: str,
    environment: dict[str, str],
    upstream: dict[str, bytes],
) -> dict[str, Any]:
    install_environment = dict(environment)
    install_environment.pop("UV_OFFLINE", None)
    with tempfile.TemporaryDirectory(prefix="scaffoldctl-phase2-backend-") as temporary:
        base = Path(temporary)
        wheel = base / "scaffoldctl-0.2.0-py3-none-any.whl"
        wheel.write_bytes(upstream["dist/scaffoldctl-0.2.0-py3-none-any.whl"])
        virtualenv = base / "venv"
        _command(
            [uv, "venv", "--python", sys.executable, os.fspath(virtualenv)],
            environment=environment,
        )
        python = virtualenv / "bin/python"
        _command(
            [
                uv,
                "pip",
                "install",
                "--python",
                os.fspath(python),
                os.fspath(wheel),
            ],
            environment=install_environment,
        )
        clean_environment = {
            key: value
            for key, value in environment.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
        }
        output = _command(
            [
                os.fspath(python),
                "-I",
                "-c",
                (
                    "import json, scaffoldctl; "
                    "assert scaffoldctl.__version__ == '0.2.0'; "
                    "print(json.dumps({'status':'pass','version':scaffoldctl.__version__}))"
                ),
            ],
            environment=clean_environment,
            cwd=base,
        )
    return {
        **json.loads(output.strip()),
        "wheelSha256": PHASE_THREE_UPSTREAM_WHEEL_SHA256,
    }


_WHEEL_SMOKE_CODE = r"""
import json, subprocess
from pathlib import Path
from scaffoldctl.git_snapshot import GitRepository
from scaffoldctl.hook import execute_pre_commit, install_hook
from scaffoldctl.ledger import DuckDbLedger
from scaffoldctl.phase2_models import BoundarySpec
from scaffoldctl.phase3_models import HookConfig, SignerProvenance
from scaffoldctl.policy import render_boundary
from scaffoldctl.semantics import PACKAGE_VERSION
assert PACKAGE_VERSION == '0.3.0'
root = Path('repository').resolve(); root.mkdir()
subprocess.run(['git', '-C', str(root), 'init', '--quiet'], check=True)
subprocess.run(
    ['git', '-C', str(root), 'config', 'user.email', 'wheel@example.invalid'], check=True
)
subprocess.run(
    ['git', '-C', str(root), 'config', 'user.name', 'wheel smoke'], check=True
)
boundary = BoundarySpec(boundaryId='wheel', targetPath='.', title='Wheel', purpose='Verify wheel')
for name, data in render_boundary(boundary).items(): (root / name).write_bytes(data)
subprocess.run(['git', '-C', str(root), 'add', '--all'], check=True)
subprocess.run(['git', '-C', str(root), 'commit', '--quiet', '-m', 'baseline'], check=True)
install_hook(str(root))
git_dir = root / '.git'
key = git_dir / 'scaffoldctl/lease-signing-key.pem'
ledger = git_dir / 'scaffoldctl/evidence.duckdb'
config = HookConfig(
    schemaId='urn:scaffoldctl:schema:hook-config:0.3.0',
    schemaVersion='0.3.0',
    repositoryRoot=str(root),
    ledgerPath=str(ledger),
    privateKeyPath=str(key),
    baselineTree='HEAD',
    leaseTtlSeconds=300,
    signerProvenance=SignerProvenance.LOCAL_REPOSITORY_KEY,
)
(root / 'README.md').write_text('\n'.join(f'line {item}' for item in range(120)))
assert execute_pre_commit(config).exitCode == 0
subprocess.run(['git', '-C', str(root), 'add', 'README.md'], check=True)
assert execute_pre_commit(config).exitCode == 1
verified = DuckDbLedger(ledger).verify()
assert verified.validationReceiptCount == 2 and verified.assetLeaseCount == 1
print(json.dumps({'assetLeases': 1, 'stagedEscapeBlocked': True, 'status': 'pass'}))
"""


def _wheel_smoke(uv: str, environment: dict[str, str]) -> dict[str, Any]:
    install_environment = dict(environment)
    install_environment.pop("UV_OFFLINE", None)
    with tempfile.TemporaryDirectory(prefix="scaffoldctl-phase3-wheel-") as temporary:
        base = Path(temporary)
        virtualenv = base / "venv"
        _command(
            [uv, "venv", "--python", sys.executable, os.fspath(virtualenv)], environment=environment
        )
        python = virtualenv / "bin/python"
        _command(
            [
                uv,
                "pip",
                "install",
                "--python",
                os.fspath(python),
                os.fspath(DIST / WHEEL_NAME),
            ],
            environment=install_environment,
        )
        code = _WHEEL_SMOKE_CODE
        clean_environment = {
            key: value
            for key, value in environment.items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}
        }
        output = _command(
            [os.fspath(python), "-I", "-c", code],
            environment=clean_environment,
            cwd=base,
        )
    return json.loads(output.strip().splitlines()[-1])


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", "-C", os.fspath(root), *arguments),
        check=True,
        capture_output=True,
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    )


def _release_ledger() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="scaffoldctl-phase3-ledger-") as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        _git(root, "init", "--quiet")
        boundary = BoundarySpec(
            boundaryId="phase3-release",
            targetPath=".",
            title="Phase 3 Release",
            purpose="Bind immutable release perimeter evidence",
        )
        for name, data in render_boundary(boundary).items():
            root.joinpath(name).write_bytes(data)
        _git(root, "add", "--all")
        repository = GitRepository(root)
        original_clock = perimeter_module.utc_now
        perimeter_module.utc_now = lambda: RELEASE_TIMESTAMP
        try:
            validation = perimeter_module.validate_index_snapshot(repository)
        finally:
            perimeter_module.utc_now = original_clock
        seed = hashlib.sha256(b"scaffoldctl-0.3.0-reproducible-evidence-only-key").digest()
        key = Ed25519PrivateKey.from_private_bytes(seed)
        lease = sign_asset_lease(
            validation,
            key,
            LeasePurpose.PRE_COMMIT,
            SignerProvenance.CI_EPHEMERAL_KEY,
            now=RELEASE_TIME,
        )
        ledger = DuckDbLedger(EVIDENCE / "phase3_ledger.duckdb")
        append = ledger.append_validation(validation, lease)
        before = ledger.verify()
        seal = ledger.seal(key, SignerProvenance.CI_EPHEMERAL_KEY, now=RELEASE_TIME)
        after = ledger.verify()
    return (
        validation.model_dump(mode="json"),
        lease.model_dump(mode="json"),
        append.model_dump(mode="json"),
        {
            "beforeSeal": before.model_dump(mode="json"),
            "seal": seal.model_dump(mode="json"),
            "afterSeal": after.model_dump(mode="json"),
        },
    )


def _lifecycle() -> dict[str, Any]:
    controller = LifecycleController(LifecycleState.PLANNED)
    receipts = []
    for trigger, evidence_id in (
        (LifecycleTrigger.SCAFFOLD, "SCF-PHASE3-COMPILED"),
        (LifecycleTrigger.VALIDATE, "SCF-PHASE3-VALIDATED"),
        (LifecycleTrigger.SEAL, "SCF-PHASE3-SEALED"),
    ):
        receipt = controller.advance(
            TransitionRequest(
                trigger=trigger,
                criteria=(
                    CriterionEvidence(
                        criterionIri=f"urn:scaffoldctl:criterion:{trigger.value}",
                        evidenceId=evidence_id,
                        admitted=True,
                    ),
                ),
            )
        )
        if not receipt.transitionAdmitted:
            raise RuntimeError("lifecycle transition was not admitted")
        receipts.append(receipt.model_dump(mode="json"))
    if controller.state is not LifecycleState.SEALED:
        raise RuntimeError("release lifecycle did not reach Sealed")
    payload = {
        "finalState": controller.state.value,
        "initialState": LifecycleState.PLANNED.value,
        "releaseDisposition": "VALIDATED_SEALED",
        "transitions": receipts,
    }
    return {**payload, "receiptSetHash": hash_payload(payload)}


def _project_files(*, include_manifest: bool) -> tuple[Path, ...]:
    selected = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise RuntimeError(f"release symlink rejected: {relative.as_posix()}")
        if not path.is_file() or path.name in {".coverage", "SHA256SUMS"}:
            continue
        if not include_manifest and relative.as_posix() == "evidence/artifact_manifest.json":
            continue
        selected.append(path)
    return tuple(sorted(selected, key=lambda item: item.relative_to(ROOT).as_posix()))


def _artifact_type(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    if path.suffix == ".duckdb":
        return "duckdb_ledger"
    if path.suffix in {".whl", ".gz"}:
        return "distribution"
    if path.suffix in {".json", ".jsonl"}:
        return "structured_evidence"
    if path.suffix in {".md", ".yml"} or path.name == "pre-commit":
        return "governance_or_adapter"
    return "package_metadata"


def _manifest(upstream: dict[str, bytes]) -> dict[str, Any]:
    artifacts = []
    current = set()
    for path in _project_files(include_manifest=False):
        relative = path.relative_to(ROOT).as_posix()
        current.add(relative)
        digest = _sha256(path)
        inherited = upstream.get(relative)
        disposition = (
            "new"
            if inherited is None
            else "inherited"
            if _sha256_bytes(inherited) == digest
            else "modified"
        )
        artifacts.append(
            {
                "artifactDisposition": disposition,
                "artifactType": _artifact_type(path),
                "path": relative,
                "sha256": digest,
                "sizeBytes": path.stat().st_size,
            }
        )
    removed = [
        {"path": path, "sha256": _sha256_bytes(data)}
        for path, data in sorted(upstream.items())
        if path not in current
        and path not in {"evidence/SHA256SUMS", "evidence/artifact_manifest.json"}
    ]
    counts = Counter(item["artifactDisposition"] for item in artifacts)
    payload = {
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
        "baselineFilesNotCarriedForward": removed,
        "dispositionCounts": dict(sorted(counts.items())),
        "generatedAtUtc": RELEASE_TIMESTAMP,
        "manifestId": "scaffoldctl-phase-3-artifact-manifest-v0.3.0",
        "provenanceId": PROVENANCE_ID,
        "upstreamArchiveSha256": PHASE_THREE_UPSTREAM_ARCHIVE_SHA256,
    }
    return {**payload, "manifestHash": hash_payload(payload)}


def _provenance(upstream: dict[str, bytes]) -> bytes:
    source = upstream.get("evidence/provenance_ledger.jsonl", b"")
    events = [parse_strict_json(line) for line in source.splitlines() if line]
    start = 0 if not events else int(events[-1]["monotonicSequence"]) + 1
    actions = (
        "PHASE_TWO_ARCHIVE_AND_WHEEL_VERIFIED",
        "PHASE_THREE_GIT_PERIMETER_VALIDATED",
        "PHASE_THREE_DUCKDB_LEDGER_SEALED",
        "PHASE_THREE_DISTRIBUTIONS_REPRODUCED",
        "PHASE_THREE_VALIDATED_SEALED",
    )
    for offset, action in enumerate(actions):
        events.append(
            {
                "action": action,
                "evidenceId": f"SCF-PHASE3-EVIDENCE-{offset:03d}",
                "monotonicSequence": start + offset,
                "provenanceId": PROVENANCE_ID,
                "status": "pass",
                "timestampUtc": RELEASE_TIMESTAMP,
            }
        )
    return b"".join(canonical_json_bytes(event) + b"\n" for event in events)


def _checksums() -> None:
    lines = [
        f"{_sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in _project_files(include_manifest=True)
    ]
    _atomic_bytes(EVIDENCE / "SHA256SUMS", ("\n".join(lines) + "\n").encode(), mode=0o644)


def _write_authority_evidence() -> None:
    ontology = verify_ontology_authority()
    resources = verify_phase_two_resource_authority()
    _atomic_json(EVIDENCE / "phase_0_baseline.json", PHASE_0_BASELINE)
    _atomic_json(EVIDENCE / "phase_2_build_authority.json", PHASE_2_BUILD_AUTHORITY)
    _atomic_json(EVIDENCE / "phase_3_build_authority.json", PHASE_3_BUILD_AUTHORITY)
    _atomic_json(EVIDENCE / "ontology_authority_receipt.json", ontology)
    _atomic_json(EVIDENCE / "phase_2_resource_authority_receipt.json", resources)
    upstream_receipt = {
        "actualArchiveSha256": PHASE_THREE_UPSTREAM_ARCHIVE_SHA256,
        "actualWheelSha256": PHASE_THREE_UPSTREAM_WHEEL_SHA256,
        "reasonCodes": ["SCF.PHASE3.UPSTREAM_VERIFIED", "SCF.PHASE3.UPSTREAM_TOKEN_MALFORMED"],
        "submittedToken": PHASE_THREE_SUBMITTED_TOKEN,
        "submittedTokenAccepted": False,
        "validationStatus": "pass",
    }
    _atomic_json(
        EVIDENCE / "upstream_verification_receipt.json",
        {**upstream_receipt, "receiptHash": hash_payload(upstream_receipt)},
    )


def _evidence_environment() -> dict[str, str]:
    environment = os.environ.copy()
    uv_cache = environment.get(
        "UV_CACHE_DIR",
        os.fspath(Path(tempfile.gettempdir()) / "scaffoldctl-phase3-uv-cache"),
    )
    environment.update(
        {
            "COVERAGE_FILE": os.fspath(Path(tempfile.gettempdir()) / "scaffoldctl-phase3.coverage"),
            "PYTHONPATH": os.fspath(ROOT / "src"),
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "UV_CACHE_DIR": uv_cache,
            "UV_OFFLINE": "1",
        }
    )
    return environment


def _coverage_gate(environment: dict[str, str], minimum: float) -> tuple[int, dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="scaffoldctl-phase3-coverage-") as temporary:
        raw_coverage = Path(temporary) / "coverage.json"
        output = _command(
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov=scaffoldctl",
                f"--cov-report=json:{raw_coverage}",
                "--cov-report=term-missing",
            ],
            environment=environment,
        )
        return _test_count(output), _coverage(raw_coverage, minimum)


def _run_gates(
    upstream: dict[str, bytes],
    minimum_coverage: float,
) -> dict[str, Any]:
    environment = _evidence_environment()
    uv = _tool("uv")
    ruff = _tool("ruff")
    _command([uv, "lock", "--check", "--offline"], environment=environment)
    _command([ruff, "check", "."], environment=environment)
    upstream_smoke = _upstream_wheel_smoke(uv, environment, upstream)
    test_count, coverage = _coverage_gate(environment, minimum_coverage)
    reproducibility = _build_twice(uv, environment)
    smoke = _wheel_smoke(uv, environment)
    validation, lease, append, ledger = _release_ledger()
    return {
        "append": append,
        "coverage": coverage,
        "ledger": ledger,
        "lease": lease,
        "lifecycle": _lifecycle(),
        "reproducibility": reproducibility,
        "smoke": smoke,
        "test_count": test_count,
        "upstream_smoke": upstream_smoke,
        "validation": validation,
    }


def _write_execution_evidence(results: dict[str, Any]) -> None:
    outputs = {
        "coverage_summary.json": results["coverage"],
        "distribution_reproducibility.json": results["reproducibility"],
        "upstream_backend_smoke.json": results["upstream_smoke"],
        "installed_wheel_smoke.json": results["smoke"],
        "phase3_perimeter_receipt.json": results["validation"],
        "phase3_asset_lease.json": results["lease"],
        "phase3_ledger_append_receipt.json": results["append"],
        "phase3_ledger_verification.json": results["ledger"],
        "lifecycle_transition_receipts.json": results["lifecycle"],
    }
    for name, payload in outputs.items():
        _atomic_json(EVIDENCE / name, payload)


def _report_payload(results: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage": results["coverage"],
        "distributionReproducibility": results["reproducibility"],
        "finalLifecycleState": "Sealed",
        "gates": (
            "upstream_archive_and_wheel",
            "out_of_band_phase_2_backend_smoke",
            "authority",
            "lint",
            "tests",
            "git_index_escape",
            "duckdb_replay",
            "signed_lease",
            "signed_ledger_seal",
            "installed_wheel",
            "reproducible_distributions",
        ),
        "ontologySha256": ONTOLOGY_SHA256,
        "packageVersion": PACKAGE_VERSION,
        "policyPackSha256": PHASE_TWO_POLICY_PACK_SHA256,
        "recordedAtUtc": RELEASE_TIMESTAMP,
        "releaseDisposition": "VALIDATED_SEALED",
        "templatePackSha256": PHASE_TWO_TEMPLATE_PACK_SHA256,
        "testsPassed": results["test_count"],
        "validationStatus": "pass",
    }


def _write_handoff(results: dict[str, Any]) -> None:
    reproducibility = results["reproducibility"]
    handoff = MachineHandoffResponse(
        response=MachineHandoffBody(
            agent_role="chief_generative_systems_architect_ssot_authority",
            task_owned="scaffoldctl_git_perimeter_and_duckdb_seal",
            implementation=(
                "pure Git-index and commit-tree object matrices",
                "fail-closed native pre-commit and pinned CI adapters",
                "Ed25519 validation-bound asset leases",
                "transactional DuckDB evidence chain and signed ledger seal",
            ),
            risks=("local hooks remain bypassable; protected CI is authoritative",),
            assumptions=("deployment binds trusted release keys outside this package",),
            follow_up_instructions=("require the scaffoldctl-perimeter protected check",),
            validation_status=ValidationStatus.PASS,
            artifact_refs=(
                f"{WHEEL_NAME} sha256:{reproducibility['distributions'][WHEEL_NAME]}",
                f"{SDIST_NAME} sha256:{reproducibility['distributions'][SDIST_NAME]}",
            ),
            provenance_id=PROVENANCE_ID,
        )
    )
    _atomic_json(EVIDENCE / "machine_handoff.json", handoff)


def _finalize_evidence(upstream: dict[str, bytes], results: dict[str, Any]) -> None:
    payload = _report_payload(results)
    report = {**payload, "reportHash": hash_payload(payload)}
    _atomic_json(EVIDENCE / "validation_report.json", report)
    _write_handoff(results)
    _atomic_bytes(EVIDENCE / "provenance_ledger.jsonl", _provenance(upstream), mode=0o644)
    _atomic_json(EVIDENCE / "artifact_manifest.json", _manifest(upstream))
    _checksums()
    reproducibility = results["reproducibility"]
    summary = {
        "coveragePercent": results["coverage"]["observedPercent"],
        "releaseDisposition": "VALIDATED_SEALED",
        "sdistSha256": reproducibility["distributions"][SDIST_NAME],
        "testsPassed": results["test_count"],
        "wheelSha256": reproducibility["distributions"][WHEEL_NAME],
    }
    print(canonical_json_bytes(summary).decode())


def main() -> int:
    arguments = _arguments()
    if not 0 < arguments.minimum_coverage <= 100:
        raise ValueError("minimum coverage must be in (0, 100]")
    upstream = _upstream_files(arguments.upstream_archive.resolve())
    _clean_outputs()
    _write_authority_evidence()
    results = _run_gates(upstream, arguments.minimum_coverage)
    _write_execution_evidence(results)
    _finalize_evidence(upstream, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
