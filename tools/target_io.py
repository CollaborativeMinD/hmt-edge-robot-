"""REQ-CD5-03: bounded duplicate-free evidence I/O and strict source admission."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ci_admission import confined, digest
from deployment_receipts import content_hash
from target_profile import TargetPolicy
from truth_serum_runtime.gates.data_parse import loads_json


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
        raise ValueError("TARGET_INPUT_BOUNDS")
    with path.open("rb") as stream:
        data = stream.read(1048577)
    if len(data) > 1048576:
        raise ValueError("TARGET_INPUT_BOUNDS")
    value = loads_json(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("TARGET_OBJECT_REQUIRED")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError("TARGET_OUTPUT_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".target-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def output_path(root: Path, path: Path, inputs: tuple[Path, ...] = ()) -> Path:
    destination = path if path.is_absolute() else root / path
    if ".." in destination.parts or destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
        raise ValueError("TARGET_OUTPUT_PATH_INVALID")
    if not destination.resolve().is_relative_to((root / "evidence/cd/stage5").resolve()):
        raise ValueError("TARGET_OUTPUT_SCOPE")
    if destination.resolve() in {p.resolve() for p in inputs}:
        raise ValueError("TARGET_OUTPUT_OVERLAPS_INPUT")
    return destination


def bind(root: Path) -> tuple[TargetPolicy, str]:
    from target_bindings import verify
    from target_contracts import Capture
    from target_owner import OwnerInventory
    from target_receipts import Outcome

    catalog = read_json(confined(root, "policy/target_admission.json"))
    if set(catalog) != {"schema_version", "scope", "files"} or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1 or catalog["scope"] != "READ_ONLY_TARGET_QUALIFICATION":
        raise ValueError("TARGET_CATALOG_SCHEMA")
    files = catalog["files"]
    if not isinstance(files, dict) or not 1 <= len(files) <= 32:
        raise ValueError("TARGET_CATALOG_BOUNDS")
    sources = {str(p.relative_to(root)) for p in (root / "tools").glob("target_*.py")}
    required = sources | {"policy/target.json", "docs/cd/target-policy.schema.json", "docs/cd/target-capture.schema.json", "docs/cd/owner-inventory.schema.json", "docs/cd/target-receipt.schema.json", "docs/cd/target-field-bindings.json", "docs/cd/stage5.md", "docs/cd/owner-inventory.json"}
    if set(files) != required:
        raise ValueError("TARGET_CATALOG_INVENTORY")
    for name, expected in files.items():
        if digest(confined(root, name)) != expected:
            raise ValueError("TARGET_SOURCE_DRIFT")
    for name, model in (("target-policy", TargetPolicy), ("target-capture", Capture), ("owner-inventory", OwnerInventory)):
        if read_json(root / f"docs/cd/{name}.schema.json") != model.model_json_schema():
            raise ValueError("TARGET_SCHEMA_DRIFT")
    if read_json(root / "docs/cd/target-receipt.schema.json") != Outcome.json_schema():
        raise ValueError("TARGET_SCHEMA_DRIFT")
    verify(root)
    policy = TargetPolicy.model_validate_json(json.dumps(read_json(root / "policy/target.json")))
    return policy, content_hash({name: files[name] for name in sorted(sources)})
