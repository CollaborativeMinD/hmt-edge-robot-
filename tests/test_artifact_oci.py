"""OCI closure rejects byte tampering, unsafe tar members, and platform drift."""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest
from artifact_oci import blob, inspect
from artifact_support import COMMIT, oci


def test_oci_content_closure_is_verified(tmp_path: Path) -> None:
    image, config = oci(tmp_path)
    assert inspect(tmp_path / "image.oci.tar", COMMIT) == (image, config)
    with pytest.raises(ValueError, match="COMMIT_MISMATCH"):
        inspect(tmp_path / "image.oci.tar", "3" * 40)


@pytest.mark.parametrize("fault", ["tamper", "escape", "link", "duplicate", "architecture", "os"])
def test_unsafe_or_contradictory_archive_is_rejected(tmp_path: Path, fault: str) -> None:
    oci(tmp_path)
    path = tmp_path / "image.oci.tar"
    with tarfile.open(path) as archive:
        files = {}
        for member in archive.getmembers():
            stream = archive.extractfile(member)
            assert stream is not None
            files[member.name] = stream.read()
    if fault == "tamper":
        key = next(n for n, data in files.items() if data == b"layer")
        files[key] = b"wrong"
    if fault in ("architecture", "os"):
        index = json.loads(files["index.json"])
        index["manifests"][0]["platform"]["architecture" if fault == "architecture" else "os"] = "wrong"
        files["index.json"] = json.dumps(index).encode()
    with tarfile.open(path, "w") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if fault in ("escape", "link", "duplicate"):
            member = tarfile.TarInfo("../escape" if fault == "escape" else "index.json")
            if fault == "link":
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
            archive.addfile(member)
    with pytest.raises(ValueError):
        inspect(path, COMMIT)


@pytest.mark.parametrize("digest,size", [("latest", 1), ("sha256:" + "z" * 64, 1),
    ("sha256:" + "1" * 64, 9)])
def test_blob_descriptor_is_bounded(tmp_path: Path, digest: str, size: int) -> None:
    oci(tmp_path)
    with tarfile.open(tmp_path / "image.oci.tar") as archive:
        with pytest.raises((ValueError, KeyError)):
            blob(archive, {"digest": digest, "size": size})


def test_nested_oci_index_preserves_content_identity(tmp_path: Path) -> None:
    import hashlib
    image, config = oci(tmp_path)
    path = tmp_path / "image.oci.tar"
    with tarfile.open(path) as archive:
        stream = archive.extractfile("index.json")
        assert stream is not None
        index = stream.read()
    index_hash = hashlib.sha256(index).hexdigest()
    with tarfile.open(path, "a") as archive:
        member = tarfile.TarInfo("blobs/sha256/" + index_hash)
        member.size = len(index)
        archive.addfile(member, io.BytesIO(index))
    # Rebuild the outer index rather than appending a duplicate name.
    with tarfile.open(path) as archive:
        files = []
        for member in archive.getmembers():
            stream = archive.extractfile(member)
            assert stream is not None
            files.append((member.name, stream.read()))
    outer = json.dumps({"manifests": [{"mediaType": "application/vnd.oci.image.index.v1+json",
        "digest": "sha256:" + index_hash, "size": len(index)}]}).encode()
    with tarfile.open(path, "w") as archive:
        for name, data in files:
            data = outer if name == "index.json" else data
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    assert inspect(path, COMMIT) == (image, config)
