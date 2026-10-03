"""Independent mutations of reviewed design artifacts for adversarial tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from ci_admission import ROOT


def deployment_copy(tmp_path: Path) -> Path:
    catalog = json.loads((ROOT / "policy/deployment_admission.json").read_text())
    for name in ["policy/deployment_admission.json", *catalog["inputs"], *catalog["runtime_sources"]]:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return tmp_path


def rewrite(root: Path, name: str, value: object, repin: bool = False) -> None:
    path = root / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    if repin:
        catalog_path = root / "policy/deployment_admission.json"
        catalog = json.loads(catalog_path.read_text())
        catalog["inputs"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        catalog_path.write_text(json.dumps(catalog))


def mutate(root: Path, name: str, keys: tuple[str | int, ...], value: object) -> None:
    data = json.loads((root / name).read_text())
    parent: Any = data
    for key in keys[:-1]:
        parent = parent[key]
    parent[keys[-1]] = value
    rewrite(root, name, data, repin=True)
