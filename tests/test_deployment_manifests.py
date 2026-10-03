"""Authority checks survive a proposed rehash of malicious manifest bytes."""

from __future__ import annotations

from pathlib import Path

import pytest
from deployment_admission import evaluate
from deployment_support import deployment_copy, mutate

WORKLOAD = "deploy/stage3/workload/workload.template.json"


@pytest.mark.parametrize("keys,value", [
    (("spec", "replicas"), 1), (("spec", "replicas"), False),
    (("spec", "strategy", "type"), "RollingUpdate"),
    (("spec", "template", "spec", "hostNetwork"), True),
    (("spec", "template", "spec", "automountServiceAccountToken"), True),
    (("spec", "template", "spec", "containers", 0, "image"), "example:latest"),
    (("spec", "template", "spec", "containers", 0, "securityContext", "privileged"), True),
    (("spec", "template", "spec", "containers", 0, "securityContext", "allowPrivilegeEscalation"), True),
    (("spec", "template", "spec", "containers", 0, "securityContext", "readOnlyRootFilesystem"), False),
    (("spec", "template", "spec", "containers", 0, "env", 0), {"name": "HMT_API_TOKEN", "value": "inline-secret"}),
    (("spec", "template", "spec", "containers", 0, "readinessProbe", "exec", "command"), ["true"]),
    (("spec", "template", "spec", "volumes", 0), {"name": "ledger", "hostPath": {"path": "/"}}),
])
def test_manifest_cannot_widen_runtime_authority(tmp_path: Path, keys: tuple[str | int, ...], value: object) -> None:
    root = deployment_copy(tmp_path)
    mutate(root, WORKLOAD, keys, value)
    with pytest.raises(ValueError, match="MANIFEST_AUTHORITY_OR_CONTRACT_DRIFT"):
        evaluate(root)


@pytest.mark.parametrize("name,keys,value", [
    ("deploy/stage3/flux/source.template.json", ("spec", "suspend"), False),
    ("deploy/stage3/flux/source.template.json", ("spec", "ref"), {"branch": "main"}),
    ("deploy/stage3/flux/reconcile.template.json", ("spec", "suspend"), 1),
    ("deploy/stage3/flux/reconcile.template.json", ("spec", "prune"), True),
    ("deploy/stage3/flux/reconcile.template.json", ("spec", "serviceAccountName"), "cluster-admin"),
    ("deploy/stage3/flux/rbac.json", ("items", 1, "rules", 0, "verbs"), ["*"]),
    ("deploy/stage3/workload/networkpolicy.json", ("spec", "egress"), [{}]),
    ("deploy/stage3/workload/pvc.json", ("spec", "accessModes"), ["ReadWriteMany"]),
    ("deploy/stage3/workload/pvc.json", ("metadata", "annotations", "kustomize.toolkit.fluxcd.io/prune"), "enabled"),
    ("deploy/stage3/workload/kustomization.yaml", ("resources",), ["../../outside.yaml"]),
    ("docs/cd/release-receipt.schema.json", ("additionalProperties",), True),
])
def test_manifest_cannot_widen_reconciliation_storage_or_network(tmp_path: Path, name: str, keys: tuple[str | int, ...], value: object) -> None:
    root = deployment_copy(tmp_path)
    mutate(root, name, keys, value)
    with pytest.raises(ValueError, match="MANIFEST_AUTHORITY_OR_CONTRACT_DRIFT"):
        evaluate(root)
