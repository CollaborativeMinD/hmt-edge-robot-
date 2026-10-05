"""Require complete scanner evidence, locked runtime packages, and signed provenance."""
from __future__ import annotations

import tomllib
from typing import Any

from artifact_waivers import admit


def dictionaries(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value, *[d for v in value.values() for d in dictionaries(v)]]
    if isinstance(value, list):
        return [d for v in value for d in dictionaries(v)]
    return []


def scans(sbom: dict, scan: dict, probe: dict, lock: bytes, waiver: dict | None = None) -> list[dict]:
    if sbom.get("spdxVersion") != "SPDX-2.3" or not sbom.get("packages"):
        raise ValueError("SBOM_INCOMPLETE")
    if scan.get("SchemaVersion") != 2 or scan.get("ArtifactType") != "container_image":
        raise ValueError("SCAN_SCHEMA_INCOMPLETE")
    results = scan.get("Results")
    if not isinstance(results, list) or not {"os-pkgs", "lang-pkgs"} <= {r.get("Class") for r in results}:
        raise ValueError("SCAN_COVERAGE_INCOMPLETE")
    exceptions = admit(scan, waiver)
    if probe.get("status") != "PASS" or probe.get("platform") != "aarch64" or probe.get("uid") != 10001:
        raise ValueError("NATIVE_CONTAINER_QUALIFICATION_FAILED")
    if probe.get("minimal_runtime") is not True or probe.get("native_features") != "PASS":
        raise ValueError("MINIMAL_RUNTIME_QUALIFICATION_FAILED")
    if probe.get("paid_calls") != 0 or probe.get("resident_stopped") is not True:
        raise ValueError("RESIDENT_BOUNDARY_FAILED")
    if probe.get("events", 0) <= 0 or probe["events"] != probe.get("replayed"):
        raise ValueError("CONTAINER_REPLAY_FAILED")
    packages = {p["name"]: p["version"] for p in tomllib.loads(lock.decode())["package"]}
    installed = probe.get("packages")
    if not isinstance(installed, dict) or installed.get("hmt-edge-robot") != packages["hmt-edge-robot"]:
        raise ValueError("INSTALLED_PACKAGE_MISSING")
    for name, version in installed.items():
        if name not in ("pip", "setuptools") and packages.get(name) != version:
            raise ValueError("INSTALLED_LOCK_DIVERGED")
    names = {p["name"].lower().replace("_", "-"): p.get("versionInfo") for p in sbom["packages"]}
    if any(names.get(name) != version for name, version in installed.items() if name not in ("pip", "setuptools")):
        raise ValueError("SBOM_RUNTIME_PACKAGE_DIVERGED")
    return exceptions


def provenance(value: object, archive_hash: str, commit: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("SIGNED_PROVENANCE_MISSING")
    statements = [d for d in dictionaries(value) if d.get("predicateType") == "https://slsa.dev/provenance/v1"]
    for statement in statements:
        subjects = statement.get("subject", [])
        if not any(s.get("digest", {}).get("sha256") == archive_hash for s in subjects):
            continue
        predicate = statement.get("predicate", {})
        definition = predicate.get("buildDefinition", {})
        workflow = definition.get("externalParameters", {}).get("workflow", {})
        sources = definition.get("resolvedDependencies", [])
        correct_source = any(d.get("digest", {}).get("gitCommit") == commit for d in sources)
        if correct_source and workflow.get("repository") == "https://github.com/CollaborativeMinD/hmt-edge-robot-" and workflow.get("path") == ".github/workflows/artifact.yml":
            return
    raise ValueError("PROVENANCE_SUBJECT_OR_SOURCE_MISMATCH")
