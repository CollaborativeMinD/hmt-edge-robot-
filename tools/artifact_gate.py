"""Fail-closed artifact qualification; signed evidence must be verified by the workflow."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from artifact_contracts import ArtifactReceipt
from artifact_evidence import provenance
from artifact_preflight import assess
from artifact_verify import verify_signature
from ci_admission import ROOT, confined, digest
from deployment_receipts import content_hash


def check_signing(root: Path) -> None:
    policy = json.loads(confined(root, "policy/artifact_signing.json").read_text())
    if policy.get("backend") != "github_native_private_sigstore" or policy.get("status") != "ADMITTED":
        raise ValueError("SIGNING_BACKEND_NOT_ADMITTED")


def evaluate(root: Path, commit: str) -> ArtifactReceipt:
    report = assess(root, commit)
    check_signing(root)
    archive = root / "evidence/cd/stage4/image.oci.tar"
    signature = verify_signature(archive, commit)
    provenance(signature, report["archive_sha256"], commit)
    inputs = {**report["inputs"], "provenance-verification.json": digest(confined(root, "evidence/cd/stage4/provenance-verification.json"))}
    payload = {"schema_version": 1, "status": "PASS", "stage": 4, "source_commit": commit,
        "image_digest": report["image_digest"], "archive_sha256": report["archive_sha256"], "inputs": inputs,
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
        message = str(exc)
        safe_code = type(exc) is ValueError and message.isupper() and message.replace("_", "").isalnum()
        rejection["reason_codes"] = [message if safe_code else type(exc).__name__ + ":ARTIFACT_QUALIFICATION_REJECTED"]
        report = rejection
    persist(root, report)
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(ROOT, sys.argv[1] if len(sys.argv) > 1 else None))
