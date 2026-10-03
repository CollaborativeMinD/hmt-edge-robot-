"""Bounded input reads and an independently reviewed local source catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from ci_admission import confined, digest
from deployment_contracts import Baseline, Closed, Hash
from deployment_receipts import content_hash
from pydantic import Field
from truth_serum_runtime.gates.data_parse import loads_json


class DeploymentCatalog(Closed):
    schema_version: Literal[1]
    baseline: Baseline
    inputs: dict[str, Hash] = Field(min_length=1, max_length=32)
    runtime_sources: dict[str, Hash] = Field(min_length=1, max_length=128)


def read_object(root: Path, name: str) -> dict[str, Any]:
    path = confined(root, name)
    if path.stat().st_size > 65536:
        raise ValueError("DEPLOYMENT_INPUT_TOO_LARGE:" + name)
    value = loads_json(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("DEPLOYMENT_OBJECT_REQUIRED:" + name)
    return value


def bind_catalog(root: Path) -> DeploymentCatalog:
    catalog = DeploymentCatalog.model_validate(read_object(root, "policy/deployment_admission.json"))
    actual = {p.relative_to(root).as_posix() for p in (root / "src").rglob("*.py")}
    if actual != set(catalog.runtime_sources):
        raise ValueError("RELEASE_SOURCE_INVENTORY_MISMATCH")
    for name, expected in {**catalog.inputs, **catalog.runtime_sources}.items():
        if digest(confined(root, name)) != expected:
            raise ValueError("DEPLOYMENT_DIGEST_MISMATCH:" + name)
    return catalog


def inventory_hash(catalog: DeploymentCatalog) -> str:
    return content_hash(catalog.runtime_sources)
