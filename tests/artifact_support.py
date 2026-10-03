"""Synthetic evidence fixtures; never production qualification evidence."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

COMMIT = "1" * 40


def oci(root: Path) -> tuple[str, str]:
    files: dict[str, bytes] = {}
    def store(value: dict | bytes) -> dict:
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        digest = hashlib.sha256(raw).hexdigest()
        files["blobs/sha256/" + digest] = raw
        return {"digest": "sha256:" + digest, "size": len(raw)}
    config = store({"os": "linux", "architecture": "arm64", "config": {
        "User": "10001:10001", "Labels": {"org.opencontainers.image.revision": COMMIT}}})
    manifest = store({"config": config, "layers": [store(b"layer")]})
    files["index.json"] = json.dumps({"manifests": [{**manifest,
        "platform": {"os": "linux", "architecture": "arm64"}}]}).encode()
    destination = root / "image.oci.tar"
    with tarfile.open(destination, "w") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return manifest["digest"], config["digest"]


def signature(archive: Path) -> list:
    return [{"verificationResult": {"statement": {"predicateType": "https://slsa.dev/provenance/v1",
        "subject": [{"digest": {"sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}],
        "predicate": {"buildDefinition": {"externalParameters": {"workflow": {
            "repository": "https://github.com/CollaborativeMinD/hmt-edge-robot-",
            "path": ".github/workflows/artifact.yml"}},
            "resolvedDependencies": [{"digest": {"gitCommit": COMMIT}}]}}}}}]


def fixture(root: Path) -> Path:
    destination = root / "evidence/cd/stage4"
    destination.mkdir(parents=True)
    image, config = oci(destination)
    values = {"base-lock.json": {n: n + "@sha256:" + "2" * 64 for n in ("python", "uv", "trivy", "buildkit")},
        "sbom.spdx.json": {"spdxVersion": "SPDX-2.3", "packages": [{"name": "hmt-edge-robot", "versionInfo": "1.0.0"}]},
        "vulnerabilities.json": {"SchemaVersion": 2, "ArtifactType": "container_image",
            "Metadata": {"ImageID": config}, "Results": [{"Class": "os-pkgs"}, {"Class": "lang-pkgs"}]},
        "container.json": {"status": "PASS", "platform": "aarch64", "uid": 10001,
            "paid_calls": 0, "resident_stopped": True, "events": 3, "replayed": 3,
            "packages": {"hmt-edge-robot": "1.0.0"}},
        "build-metadata.json": {"containerimage.digest": image},
        "loaded-image.json": [{"Id": config}],
        "scan-input.json": {"Digest": image, "Architecture": "arm64", "Os": "linux"}}
    for name, value in values.items():
        (destination / name).write_text(json.dumps(value))
    for name in ("pyproject.toml", "deploy/stage4/Dockerfile", ".dockerignore"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    (root / "policy").mkdir(exist_ok=True)
    (root / "policy/artifact_signing.json").write_text(json.dumps({"backend": "github_native_private_sigstore", "status": "ADMITTED"}))
    (root / "uv.lock").write_text('[[package]]\nname="hmt-edge-robot"\nversion="1.0.0"\n')
    return destination
