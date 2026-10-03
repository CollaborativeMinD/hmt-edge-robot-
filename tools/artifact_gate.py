"""Fail-closed artifact qualification; signed evidence must be verified by the workflow."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from artifact_contracts import ArtifactReceipt
from artifact_evidence import provenance, scans
from artifact_oci import inspect
from artifact_verify import verify_signature
from ci_admission import ROOT, confined, digest
from deployment_receipts import content_hash

FILES = ("base-lock.json", "sbom.spdx.json", "vulnerabilities.json", "container.json",
         "provenance-verification.json", "build-metadata.json", "loaded-image.json", "scan-input.json")


def archive_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(2**20):
            result.update(block)
    return result.hexdigest()


def evaluate(root: Path, commit: str) -> ArtifactReceipt:
    directory = root / "evidence/cd/stage4"
    archive = directory / "image.oci.tar"
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("OCI_ARCHIVE_UNAVAILABLE")
    verify_signature(archive, commit)
    data = {name: json.loads(confined(root, "evidence/cd/stage4/" + name).read_text()) for name in FILES}
    bases = data["base-lock.json"]
    if set(bases) != {"python", "uv", "trivy", "buildkit"}:
        raise ValueError("BASE_LOCK_INCOMPLETE")
    for image in bases.values():
        if not isinstance(image, str) or "@sha256:" not in image or len(image.rsplit(":", 1)[1]) != 64:
            raise ValueError("BASE_DIGEST_REQUIRED")
    image, config = inspect(archive, commit)
    loaded = data["loaded-image.json"]
    if len(loaded) != 1 or loaded[0].get("Id") != config:
        raise ValueError("LOADED_IMAGE_NOT_QUALIFIED_ARTIFACT")
    scan_input = data["scan-input.json"]
    if scan_input.get("Digest") != image or scan_input.get("Architecture") != "arm64" or scan_input.get("Os") != "linux":
        raise ValueError("SCANNER_IMAGE_IDENTITY_MISMATCH")
    if data["vulnerabilities.json"].get("Metadata", {}).get("ImageID") != config:
        raise ValueError("SCANNER_CONFIG_IDENTITY_MISMATCH")
    metadata = data["build-metadata.json"]
    if metadata.get("containerimage.config.digest") != config:
        raise ValueError("BUILD_METADATA_CONFIG_MISMATCH")
    scans(data["sbom.spdx.json"], data["vulnerabilities.json"], data["container.json"], (root / "uv.lock").read_bytes())
    archive_digest = archive_hash(archive)
    provenance(data["provenance-verification.json"], archive_digest, commit)
    inputs = {name: digest(confined(root, "evidence/cd/stage4/" + name)) for name in FILES}
    inputs.update({name: digest(root / name) for name in ("uv.lock", "pyproject.toml", "deploy/stage4/Dockerfile", ".dockerignore")})
    payload = {"schema_version": 1, "status": "PASS", "stage": 4, "source_commit": commit,
        "image_digest": image, "archive_sha256": archive_digest, "inputs": inputs,
        "platform": "linux/arm64", "authority": "ARTIFACT_QUALIFICATION_ONLY",
        "deployment": "HOLD", "hardware": "HOLD",
        "vulnerability_disposition": "NO_HIGH_CRITICAL_OR_SECRETS;LOW_MEDIUM_RECORDED",
        "notification": "ARM64_ARTIFACT_QUALIFIED_DEPLOYMENT_HELD", "alert": False}
    return ArtifactReceipt.model_validate({**payload, "receipt_hash": content_hash(payload)})


def persist(root: Path, report: dict) -> None:
    destination = root / "evidence/cd/stage4/qualification.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)


def main(root: Path = ROOT, commit: str | None = None) -> int:
    rejection = {"status": "FAIL", "stage": 4, "deployment": "HOLD", "hardware": "HOLD",
        "reason_codes": ["ARTIFACT_QUALIFICATION_INCOMPLETE"],
        "notification": "ARM64_ARTIFACT_REJECTED", "alert": True}
    persist(root, rejection)
    try:
        report = evaluate(root, commit or os.environ.get("GITHUB_SHA", "")).model_dump(mode="json")
    except (ValueError, OSError, KeyError, TypeError, TimeoutError, subprocess.SubprocessError) as exc:
        rejection["reason_codes"] = [type(exc).__name__ + ":ARTIFACT_QUALIFICATION_REJECTED"]
        report = rejection
    persist(root, report)
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(ROOT, sys.argv[1] if len(sys.argv) > 1 else None))
