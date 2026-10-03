"""Bounded OCI traversal: verify content closure without extracting archive paths."""
from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


def blob(archive: tarfile.TarFile, descriptor: dict[str, Any], limit: int = 2**31, retain: bool = True) -> bytes:
    digest = descriptor["digest"]
    if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
        raise ValueError("OCI_DIGEST_INVALID")
    if any(c not in "0123456789abcdef" for c in digest[7:]):
        raise ValueError("OCI_DIGEST_INVALID")
    member = archive.getmember("blobs/sha256/" + digest[7:])
    if not member.isfile() or member.size != descriptor["size"] or member.size > limit:
        raise ValueError("OCI_BLOB_SIZE_INVALID")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError("OCI_BLOB_UNAVAILABLE")
    hasher = hashlib.sha256()
    blocks = []
    while block := stream.read(2**20):
        hasher.update(block)
        if retain:
            blocks.append(block)
    if hasher.hexdigest() != digest[7:]:
        raise ValueError("OCI_CONTENT_MISMATCH")
    return b"".join(blocks)



def manifests(archive: tarfile.TarFile, index: dict, depth: int = 0) -> list[dict]:
    if depth > 4:
        raise ValueError("OCI_INDEX_DEPTH_EXCEEDED")
    result = []
    for descriptor in index["manifests"]:
        if descriptor.get("mediaType") in ("application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"):
            result.extend(manifests(archive, json.loads(blob(archive, descriptor, 2**20)), depth + 1))
        else:
            result.append(descriptor)
    return result


def inspect(path: Path, commit: str) -> tuple[str, str]:
    if path.stat().st_size > 8 * 2**30:
        raise ValueError("OCI_ARCHIVE_TOO_LARGE")
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) > 4096 or len({m.name for m in members}) != len(members):
            raise ValueError("OCI_MEMBER_BOUNDS")
        if any(m.issym() or m.islnk() or m.name.startswith("/") or ".." in Path(m.name).parts for m in members):
            raise ValueError("OCI_UNSAFE_MEMBER")
        stream = archive.extractfile("index.json")
        if stream is None:
            raise ValueError("OCI_INDEX_UNAVAILABLE")
        index = json.loads(stream.read(2**20))
        images = [d for d in manifests(archive, index) if d.get("platform", {}).get("architecture") == "arm64"]
        if len(images) != 1 or images[0]["platform"]["os"] != "linux":
            raise ValueError("OCI_ARM64_REQUIRED")
        descriptor = images[0]
        manifest = json.loads(blob(archive, descriptor, 2**20))
        config = json.loads(blob(archive, manifest["config"], 2**20))
        if config["architecture"] != "arm64" or config["os"] != "linux":
            raise ValueError("OCI_CONFIG_PLATFORM_MISMATCH")
        if config["config"]["User"] != "10001:10001":
            raise ValueError("OCI_RUNTIME_USER_MISMATCH")
        if config["config"]["Labels"].get("org.opencontainers.image.revision") != commit:
            raise ValueError("OCI_SOURCE_COMMIT_MISMATCH")
        for layer in manifest["layers"]:
            blob(archive, layer, retain=False)
    return descriptor["digest"], manifest["config"]["digest"]


def root_digest(path: Path) -> str:
    with tarfile.open(path) as archive:
        stream = archive.extractfile("index.json")
        if stream is None:
            raise ValueError("OCI_INDEX_UNAVAILABLE")
        index = json.loads(stream.read(2**20))
        if len(index["manifests"]) != 1:
            raise ValueError("OCI_ROOT_DESCRIPTOR_REQUIRED")
        return index["manifests"][0]["digest"]
