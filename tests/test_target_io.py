"""REQ-CD5-03: bounds, path confinement, atomic persistence and schema coupling."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from target_io import atomic_write, bind, output_path, read_json
from target_owner import evaluate as owner_evaluate
from target_test_support import make_root


def rebind(root: Path, name: str) -> None:
    path = root / "policy/target_admission.json"
    value = json.loads(path.read_text())
    value["files"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    path.write_text(json.dumps(value))


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '[]', '{'])
def test_bounded_duplicate_free_json(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "input.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        read_json(path)
    path.write_bytes(b"x" * 1048577)
    with pytest.raises(ValueError, match="BOUNDS"):
        read_json(path)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        read_json(link)


def test_atomic_output_scope_and_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = output_path(tmp_path, Path("evidence/cd/stage5/capture.json"))
    atomic_write(destination, {"status": "FAIL"})
    assert read_json(destination)["status"] == "FAIL"
    for path in (tmp_path / "policy/target.json", tmp_path / "evidence/cd/stage5/../x.json"):
        with pytest.raises(ValueError):
            output_path(tmp_path, path)
    with pytest.raises(ValueError):
        output_path(tmp_path, destination, (destination,))
    link = tmp_path / "link"
    link.symlink_to(destination)
    with pytest.raises(ValueError):
        atomic_write(link, {})
    with pytest.raises(ValueError):
        output_path(tmp_path, link)
    def fail_replace(*args: object) -> None:
        raise OSError("write blocked")
    monkeypatch.setattr("target_io.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write(destination, {"status": "PASS"})
    assert read_json(destination)["status"] == "FAIL"
    assert not list(destination.parent.glob(".target-*"))


@pytest.mark.parametrize("change", ["version", "scope", "empty", "missing", "source", "schema"])
def test_catalog_and_schema_drift(tmp_path: Path, change: str) -> None:
    root = make_root(tmp_path)
    path = root / "policy/target_admission.json"
    catalog = json.loads(path.read_text())
    if change == "version":
        catalog["schema_version"] = True
    elif change == "scope":
        catalog["scope"] = "DEPLOY"
    elif change == "empty":
        catalog["files"] = {}
    elif change == "missing":
        catalog["files"].pop("policy/target.json")
    elif change == "source":
        (root / "tools/target_snapshot.py").write_text("# changed\n")
    else:
        (root / "docs/cd/target-capture.schema.json").write_text('{}')
        path.write_text(json.dumps(catalog))
        rebind(root, "docs/cd/target-capture.schema.json")
        catalog = json.loads(path.read_text())
    path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError):
        bind(root)


@pytest.mark.parametrize("change", ["kernel", "nodes"])
def test_owner_semantic_mismatch_even_after_rehash(tmp_path: Path, change: str) -> None:
    root = make_root(tmp_path)
    path = root / "docs/cd/owner-inventory.json"
    value = json.loads(path.read_text())
    if change == "kernel":
        value["nodes"][0]["kernel"] = "wrong"
    else:
        value["nodes"][1] = value["nodes"][0]
    path.write_text(json.dumps(value))
    rebind(root, "docs/cd/owner-inventory.json")
    with pytest.raises(ValueError):
        owner_evaluate(root)
