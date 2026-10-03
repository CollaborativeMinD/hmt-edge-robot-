"""Strict design schemas reject coercion, invented evidence and wider authority."""

from __future__ import annotations

import json
from ipaddress import IPv4Address

import pytest
from ci_admission import ROOT
from deployment_contracts import DeploymentPlan
from deployment_receipts import ReleaseCandidate


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("stage", 4), ("replicas", 1), ("replicas", False),
    ("replicas", "0"), ("workers", 2), ("flux_suspended", False), ("flux_suspended", 1),
    ("architecture", "amd64"), ("driver", "PHYSICAL"), ("image", "example:latest"),
    ("bind_host", str(IPv4Address(0))), ("extra_authority", True),
])
def test_deployment_plan_rejects_authority_and_coercion(field: str, value: object) -> None:
    plan = json.loads((ROOT / "policy/deployment.json").read_text())
    plan[field] = value
    with pytest.raises(ValueError):
        DeploymentPlan.model_validate(plan)


@pytest.mark.parametrize("field,value", [
    ("request_cpu_m", "500"), ("request_cpu_m", True), ("request_cpu_m", 2000),
    ("limit_memory_mib", 255), ("limit_cpu_m", 2001), ("limit_memory_mib", float("nan")),
])
def test_deployment_resource_budgets_are_strict_and_ordered(field: str, value: object) -> None:
    plan = json.loads((ROOT / "policy/deployment.json").read_text())
    plan["resources"]["limit_cpu_m"] = 1000
    plan["resources"][field] = value
    with pytest.raises(ValueError):
        DeploymentPlan.model_validate(plan)


def test_boundary_and_zero_hash_cannot_be_promoted() -> None:
    plan = json.loads((ROOT / "policy/deployment.json").read_text())
    plan["boundaries"]["cluster_deployment"] = "READY"
    with pytest.raises(ValueError):
        DeploymentPlan.model_validate(plan)
    plan = json.loads((ROOT / "policy/deployment.json").read_text())
    plan["baseline"]["commit"] = "0" * 40
    with pytest.raises(ValueError, match="string_pattern_mismatch"):
        DeploymentPlan.model_validate(plan)


@pytest.mark.parametrize("field,value", [
    ("schema_version", 1.0), ("authorization", "DEPLOY"), ("artifact_status", "BUILT"),
    ("image_digest", "sha256:" + "a" * 64), ("target_observation", {"qualified": True}),
    ("plan_sha256", "0" * 64),
])
def test_candidate_cannot_invent_build_or_target_evidence(field: str, value: object) -> None:
    value_map = json.loads((ROOT / "policy/release_candidate.json").read_text())
    value_map[field] = value
    with pytest.raises(ValueError):
        ReleaseCandidate.model_validate(value_map)
