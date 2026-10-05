"""Recheck the exact OCI artifact, then stage offline Pi files without secrets."""
from __future__ import annotations

import json
import os
from pathlib import Path

from appliance_process import run
from appliance_workload import manifests
from artifact_preflight import assess
from ci_admission import ROOT


def prepare(root: Path, commit: str, destination: Path) -> dict:
    report = assess(root, commit)
    repository = os.environ.get("GITHUB_REPOSITORY", "CollaborativeMinD/hmt-edge-robot-").lower().rstrip("._-")
    image = "ghcr.io/" + repository
    reference = image + "@" + report["image_digest"]
    tag = image + ":sha-" + commit
    archive_tag = "sha-" + commit
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "workload.json").write_text(json.dumps(manifests(root, reference), indent=2) + "\n")
    (destination / "namespace.json").write_text(json.dumps({"apiVersion": "v1", "kind": "Namespace",
        "metadata": {"name": "hmt-edge-robot-sil", "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}}) + "\n")
    (destination / "image-ref").write_text(reference + "\n")
    (destination / "image-tag").write_text(tag + "\n")
    run(["/usr/bin/skopeo", "copy", "--preserve-digests", "--override-arch", "arm64", "--override-os", "linux",
        "oci-archive:" + str(root / "evidence/cd/stage4/image.oci.tar"),
        "oci-archive:" + str(destination / "runtime.oci.tar") + ":" + archive_tag], timeout=300)
    staged = json.loads(run(["/usr/bin/skopeo", "inspect", "--override-arch", "arm64", "--override-os", "linux",
        "oci-archive:" + str(destination / "runtime.oci.tar")], timeout=30))
    if staged.get("Digest") != report["image_digest"] or staged.get("Architecture") != "arm64" or staged.get("Os") != "linux":
        raise ValueError("OFFLINE_RUNTIME_DIGEST_MISMATCH")
    (destination / "prequalification.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    prepare(ROOT, os.environ["GITHUB_SHA"], ROOT / "build/payload")
