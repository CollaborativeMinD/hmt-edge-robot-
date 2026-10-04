"""Detached private RSA/SHA-256 signatures with an independently pinned public key."""
from __future__ import annotations

import json
import re
from pathlib import Path

from appliance_process import run
from artifact_preflight import archive_hash


def public_key(path: Path, expected: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or archive_hash(path) != expected:
        raise ValueError("SIGNING_KEY_FINGERPRINT_MISMATCH")
    result = run(["/usr/bin/openssl", "pkey", "-pubin", "-in", str(path), "-text", "-noout"],
                            timeout=10).decode()
    if not re.search(r"Public-Key: \((3072|4096) bit\)", result) or "Modulus:" not in result:
        raise ValueError("RSA_3072_OR_4096_REQUIRED")


def verify(directory: Path, key: Path, fingerprint: str, commit: str) -> dict:
    public_key(key, fingerprint)
    manifest = directory / "release.json"
    run(["/usr/bin/openssl", "dgst", "-sha256", "-verify", str(key), "-signature",
                    str(directory / "release.sig"), str(manifest)], timeout=10)
    value = json.loads(manifest.read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or value.get("source_commit") != commit:
        raise ValueError("RELEASE_SOURCE_MISMATCH")
    if value.get("scope") != "PI_SIL_SOFTWARE_APPLIANCE" or value.get("hardware") != "HOLD" or value.get("status") != "PASS":
        raise ValueError("RELEASE_AUTHORITY_MISMATCH")
    files = value.get("files")
    required = {"hmt-edge-robot.img.xz", "image.oci.tar", "evidence.tar.gz", "inputs.json", "signing-public.pem"}
    if not isinstance(files, dict) or set(files) != required:
        raise ValueError("RELEASE_FILES_INCOMPLETE")
    if value.get("signing_key_sha256") != fingerprint or value.get("archive_sha256") != files["image.oci.tar"] or not re.fullmatch(r"sha256:[0-9a-f]{64}", value.get("image_digest", "")):
        raise ValueError("RELEASE_IDENTITY_MISMATCH")
    for name, expected in files.items():
        path = directory / name
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name) or path.is_symlink():
            raise ValueError("RELEASE_PATH_INVALID")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected) or archive_hash(path) != expected:
            raise ValueError("RELEASE_CONTENT_CHANGED")
    return value
