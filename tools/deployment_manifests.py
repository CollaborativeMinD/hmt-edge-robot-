"""Exact manifest grammar; unknown or widened Kubernetes objects are rejected."""

from __future__ import annotations

from typing import Any

from deployment_contracts import DeploymentPlan
from deployment_receipts import canonical
from deployment_workload import LABELS, workload


def manifests(plan: DeploymentPlan, runtime_policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ns = plan.namespace
    def meta(name: str) -> dict[str, str]:
        return {"name": name, "namespace": ns}
    result = {
        "namespace.json": {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": ns,
            "labels": {"pod-security.kubernetes.io/enforce": "restricted"}}},
        "serviceaccount.json": {"apiVersion": "v1", "kind": "ServiceAccount",
            "metadata": meta("hmt-edge-runtime"), "automountServiceAccountToken": False},
        "pvc.json": {"apiVersion": "v1", "kind": "PersistentVolumeClaim",
            "metadata": {**meta("hmt-edge-ledger"), "annotations": {"kustomize.toolkit.fluxcd.io/prune": "disabled"}},
            "spec": {"accessModes": [plan.storage_access_mode], "storageClassName": plan.storage_class,
                     "resources": {"requests": {"storage": f"{plan.storage_gib}Gi"}}}},
        "networkpolicy.json": {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy",
            "metadata": meta("hmt-edge-deny-all"), "spec": {"podSelector": {"matchLabels": LABELS},
            "policyTypes": ["Ingress", "Egress"], "ingress": [], "egress": []}},
        "runtime-policy.json": {"apiVersion": "v1", "kind": "ConfigMap",
            "metadata": meta("hmt-edge-runtime-policy"), "immutable": True,
            "data": {"runtime-policy.json": canonical(runtime_policy)}},
        "workload.template.json": workload(plan),
    }
    result["kustomization.yaml"] = {"apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization", "resources": sorted(set(result) - {"namespace.json"})}
    return result
