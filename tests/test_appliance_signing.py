"""Real private signatures reject changed bytes, keys, sources and release authority."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from appliance_process import run
from appliance_signature import public_key, verify
from artifact_preflight import archive_hash

COMMIT = "1" * 40


@pytest.fixture
def signed(tmp_path: Path) -> tuple[Path, Path, str]:
    private = tmp_path / "private.pem"
    public = tmp_path / "signing-public.pem"
    private.write_bytes(run(["/usr/bin/openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072"]))
    public.write_bytes(run(["/usr/bin/openssl", "pkey", "-in", str(private), "-pubout"]))
    fingerprint = archive_hash(public)
    files = {}
    for name in ("hmt-edge-robot.img.xz", "image.oci.tar", "evidence.tar.gz", "inputs.json"):
        (tmp_path / name).write_bytes(b"synthetic-test-only")
        files[name] = archive_hash(tmp_path / name)
    files[public.name] = fingerprint
    value = {"status": "PASS", "scope": "PI_SIL_SOFTWARE_APPLIANCE", "hardware": "HOLD",
             "source_commit": COMMIT, "signing_key_sha256": fingerprint, "image_digest": "sha256:" + "2" * 64,
             "archive_sha256": files["image.oci.tar"], "files": files}
    (tmp_path / "release.json").write_text(json.dumps(value))
    sign(tmp_path)
    return tmp_path, public, fingerprint


def sign(directory: Path) -> None:
    run(["/usr/bin/openssl", "dgst", "-sha256", "-sign", str(directory / "private.pem"),
         "-out", str(directory / "release.sig"), str(directory / "release.json")])


def test_real_signature_and_content_verification(signed: tuple[Path, Path, str]) -> None:
    directory, public, fingerprint = signed
    assert verify(directory, public, fingerprint, COMMIT)["status"] == "PASS"
    with pytest.raises(ValueError, match="FINGERPRINT"):
        public_key(public, "3" * 64)
    with pytest.raises(ValueError, match="SOURCE"):
        verify(directory, public, fingerprint, "4" * 40)
    (directory / "hmt-edge-robot.img.xz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="CONTENT"):
        verify(directory, public, fingerprint, COMMIT)


@pytest.mark.parametrize("field,value", [("hardware", "PASS"), ("status", "HOLD"), ("files", {}), ("image_digest", "latest"), ("signing_key_sha256", "0" * 64)])
def test_signed_contradictions_are_rejected(signed: tuple[Path, Path, str], field: str, value: object) -> None:
    directory, public, fingerprint = signed
    path = directory / "release.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(subprocess.CalledProcessError):
        verify(directory, public, fingerprint, COMMIT)
    sign(directory)
    with pytest.raises(ValueError):
        verify(directory, public, fingerprint, COMMIT)


def test_missing_signature_and_linked_content_are_rejected(signed: tuple[Path, Path, str]) -> None:
    directory, public, fingerprint = signed
    original = directory / "image.oci.tar"
    original.rename(directory / "other.tar")
    original.symlink_to(directory / "other.tar")
    with pytest.raises(ValueError, match="PATH"):
        verify(directory, public, fingerprint, COMMIT)
    (directory / "release.sig").unlink()
    with pytest.raises(subprocess.CalledProcessError):
        verify(directory, public, fingerprint, COMMIT)
