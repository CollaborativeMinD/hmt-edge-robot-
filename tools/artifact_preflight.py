"""Qualify unsigned artifact prerequisites independently of signing-service availability."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from artifact_evidence import scans
from artifact_oci import inspect, root_digest
from ci_admission import ROOT, confined, digest

FILES = ("base-lock.json", "sbom.spdx.json", "vulnerabilities.json", "container.json",
         "build-metadata.json", "loaded-image.json", "scan-input.json")


def archive_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(2**20):
            result.update(block)
    return result.hexdigest()


def assess(root: Path, commit: str) -> dict:
    directory = root / "evidence/cd/stage4"
    archive = directory / "image.oci.tar"
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("OCI_ARCHIVE_UNAVAILABLE")
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
    if metadata.get("containerimage.digest") != root_digest(archive):
        raise ValueError("BUILD_METADATA_OCI_ROOT_MISMATCH")
    waiver = json.loads(confined(root, "policy/artifact_vulnerability_waiver.json").read_text())
    exceptions = scans(data["sbom.spdx.json"], data["vulnerabilities.json"], data["container.json"], (root / "uv.lock").read_bytes(), waiver)
    archive_digest = archive_hash(archive)
    inputs = {name: digest(confined(root, "evidence/cd/stage4/" + name)) for name in FILES}
    inputs.update({name: digest(root / name) for name in ("uv.lock", "pyproject.toml", "deploy/stage4/Dockerfile", ".dockerignore",
        "tools/runtime_rootfs.py", "tools/runtime_elf.py", "tools/runtime_inventory.py", "tools/appliance_process.py",
        "tools/artifact_waivers.py", "policy/artifact_vulnerability_waiver.json")})
    return {"status": "PASS", "source_commit": commit, "image_digest": image,
        "archive_sha256": archive_digest, "inputs": inputs, "platform": "linux/arm64",
        "qualification": "HOLD", "signed_provenance": "HOLD", "deployment": "HOLD", "hardware": "HOLD",
        "notification": "UNSIGNED_ARTIFACT_PREQUALIFIED", "alert": False, "vulnerability_exceptions": exceptions}

def main(root: Path, commit: str) -> int:
    from artifact_gate import persist
    destination = root / "evidence/cd/stage4/prequalification.json"
    report: dict[str, Any] = {"status": "FAIL", "qualification": "HOLD", "deployment": "HOLD", "hardware": "HOLD", "alert": True}
    persist(root, {**report, "reason_codes": ["PREQUALIFICATION_NOT_COMPLETE"]})
    try:
        report = assess(root, commit)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        message = str(exc)
        report["reason_codes"] = [message if type(exc) is ValueError and message.isupper() and message.replace("_", "").isalnum() else "PREQUALIFICATION_REJECTED"]
    destination.write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] == "PASS":
        persist(root, {"status": "HOLD", "stage": 4, "deployment": "HOLD", "hardware": "HOLD",
            "reason_codes": ["SIGNED_PROVENANCE_NOT_ADMITTED"], "alert": True})
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(ROOT, sys.argv[1]))
