"""Bind the Pi image, OCI image and evidence before protected publication."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from appliance_process import run
from appliance_signature import pem, public_key, verify
from artifact_preflight import archive_hash, assess
from ci_admission import ROOT
from host_evidence import from_bundle


def release(root: Path, commit: str) -> Path:
    directory = root / "build/release"
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "release.json").write_text('{"status":"FAIL","reason":"RELEASE_INCOMPLETE"}\n')
    report = assess(root, commit)
    host = from_bundle(root, commit)
    if host["image_sha256"] != archive_hash(root / "build/hmt-edge-robot.img.xz"):
        raise ValueError("HOST_IMAGE_BINDING_MISSING")
    for source, name in ((root / "build/hmt-edge-robot.img.xz", "hmt-edge-robot.img.xz"),
                         (root / "evidence/cd/stage4/image.oci.tar", "image.oci.tar"),
                         (root / "build/evidence.tar.gz", "evidence.tar.gz"),
                         (root / "deploy/appliance/inputs.json", "inputs.json")):
        shutil.copyfile(source, directory / name)
    fingerprint = os.environ["HMT_SIGNING_PUBLIC_KEY_SHA256"]
    public = directory / "signing-public.pem"
    public.write_text(pem(os.environ["HMT_SIGNING_PUBLIC_KEY"], "PUBLIC KEY"))
    public_key(public, fingerprint)
    if (directory / "hmt-edge-robot.img.xz").stat().st_size >= 2**31:
        raise ValueError("GITHUB_RELEASE_ASSET_TOO_LARGE")
    manifest = {"schema_version": 1, "status": "PASS", "scope": "PI_SIL_SOFTWARE_APPLIANCE",
        "source_commit": commit, "platform": "linux/arm64", "hardware": "HOLD",
        "native_pi_acceptance": "NOT_RUN", "image_digest": report["image_digest"],
        "archive_sha256": report["archive_sha256"], "signing_key_sha256": fingerprint,
        "vulnerability_exceptions": report["vulnerability_exceptions"],
        "host_vulnerability_acceptance": host,
        "files": {p.name: archive_hash(p) for p in sorted(directory.iterdir()) if p.name not in {"release.json", "release.sig"}}}
    (directory / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="hmt-sign-") as temporary:
        private = Path(temporary) / "key.pem"
        private.write_text(pem(os.environ["HMT_SIGNING_PRIVATE_KEY"], "ENCRYPTED PRIVATE KEY"))
        private.chmod(0o600)
        run(["/usr/bin/openssl", "dgst", "-sha256", "-sign", str(private), "-passin",
                        "env:HMT_SIGNING_PASSWORD", "-out", str(directory / "release.sig"),
                        str(directory / "release.json")], timeout=10)
    verify(directory, public, fingerprint, commit)
    return directory


if __name__ == "__main__":
    release(ROOT, os.environ["GITHUB_SHA"])
