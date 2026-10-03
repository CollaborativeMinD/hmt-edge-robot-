"""Read-only deployment design assessment; not a Kubernetes admission webhook."""

from __future__ import annotations

import json
from pathlib import Path

from ci_admission import digest
from deployment_contracts import Boundaries, DeploymentPlan
from deployment_flux import flux_manifests
from deployment_io import DeploymentCatalog, bind_catalog, inventory_hash, read_object
from deployment_manifests import manifests
from deployment_receipts import ReleaseCandidate, ReleaseReceipt, canonical, content_hash

from hmt_edge_robot.contracts import Policy


def evaluate(root: Path) -> ReleaseReceipt:
    catalog = bind_catalog(root)
    plan = DeploymentPlan.model_validate(read_object(root, "policy/deployment.json"))
    candidate = ReleaseCandidate.model_validate(read_object(root, "policy/release_candidate.json"))
    if plan.baseline != catalog.baseline or candidate.baseline != catalog.baseline:
        raise ValueError("RELEASE_BASELINE_MISMATCH")
    if candidate.plan_sha256 != digest(root / "policy/deployment.json"):
        raise ValueError("RELEASE_PLAN_MISMATCH")
    if candidate.source_inventory_sha256 != inventory_hash(catalog):
        raise ValueError("RELEASE_SOURCE_BINDING_MISMATCH")
    policy = Policy.model_validate_json(json.dumps(read_object(root, "policy/deployment_runtime.json")))
    if policy.allow_cloud:
        raise ValueError("STAGE3_CLOUD_NOT_AUTHORIZED")
    expected = {**{"deploy/stage3/workload/" + k: v for k, v in manifests(plan, policy.model_dump(mode="json")).items()},
                **{"deploy/stage3/flux/" + k: v for k, v in flux_manifests(plan).items()}}
    schemas = {"deployment-plan": DeploymentPlan, "release-candidate": ReleaseCandidate,
               "release-receipt": ReleaseReceipt, "deployment-catalog": DeploymentCatalog}
    expected.update({"docs/cd/" + name + ".schema.json": model.model_json_schema()
                     for name, model in schemas.items()})
    required = {"policy/deployment.json", "policy/deployment_runtime.json", "policy/release_candidate.json",
                "policy/promotion.json", "uv.lock", "pyproject.toml", "docs/requirements.json",
                "docs/implementation_traceability.json", "docs/cd/stage3.md", *expected}
    if set(catalog.inputs) != required:
        raise ValueError("DEPLOYMENT_BINDING_SET_MISMATCH")
    actual = {p.relative_to(root).as_posix() for p in (root / "deploy/stage3").rglob("*") if p.is_file()}
    if actual != {name for name in expected if name.startswith("deploy/")}:
        raise ValueError("MANIFEST_INVENTORY_MISMATCH")
    for name, value in expected.items():
        if canonical(read_object(root, name)) != canonical(value):
            raise ValueError("MANIFEST_AUTHORITY_OR_CONTRACT_DRIFT:" + name)
    payload = {"schema_version": 1, "release_id": "stage3-" + content_hash(candidate.model_dump(mode="json"))[:24],
        "contract_status": "PASS", "release_decision": "HOLD", "baseline": catalog.baseline.model_dump(mode="json"),
        "candidate_sha256": digest(root / "policy/release_candidate.json"),
        "source_inventory_sha256": inventory_hash(catalog),
        "artifacts": {name: digest(root / name) for name in sorted({*catalog.inputs, "policy/deployment_admission.json"})},
        "boundaries": plan.boundaries.model_dump(mode="json"),
        "reason_codes": ["STAGE3_CONTRACT_VALIDATED", *["HOLD_" + k.upper() for k in Boundaries.model_fields]],
        "image_digest": None, "authority": "DESIGN_ONLY",
        "notification": "DEPLOYMENT_DESIGN_VALIDATED_EXECUTION_HELD", "alert": False}
    return ReleaseReceipt.model_validate_json(json.dumps({**payload, "receipt_hash": content_hash(payload)}))
