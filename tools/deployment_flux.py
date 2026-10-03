"""Suspended pull reconciliation; bootstrap credentials are external references."""

from __future__ import annotations

from typing import Any

from deployment_contracts import DeploymentPlan


def flux_manifests(plan: DeploymentPlan) -> dict[str, dict[str, Any]]:
    ns = plan.namespace
    return {
        "source.template.json": {"apiVersion": "source.toolkit.fluxcd.io/v1", "kind": "GitRepository",
            "metadata": {"name": "hmt-edge-source", "namespace": ns}, "spec": {
                "suspend": True, "interval": "5m", "timeout": "30s",
                "url": "ssh://git@github.com/CollaborativeMinD/hmt-edge-robot-.git",
                "ref": {"commit": "{{APPROVED_RELEASE_COMMIT_REQUIRED}}"},
                "secretRef": {"name": plan.git_secret}}},
        "reconcile.template.json": {"apiVersion": "kustomize.toolkit.fluxcd.io/v1", "kind": "Kustomization",
            "metadata": {"name": "hmt-edge-sil", "namespace": ns}, "spec": {
                "suspend": True, "interval": "5m", "timeout": "120s", "prune": False,
                "path": "./deploy/stage3/workload", "targetNamespace": ns,
                "serviceAccountName": "hmt-edge-reconciler", "wait": True,
                "sourceRef": {"kind": "GitRepository", "name": "hmt-edge-source"}}},
        "rbac.json": {"apiVersion": "v1", "kind": "List", "items": [
            {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {
                "name": "hmt-edge-reconciler", "namespace": ns}, "automountServiceAccountToken": False},
            {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role",
                "metadata": {"name": "hmt-edge-reconciler", "namespace": ns}, "rules": [
                    {"apiGroups": ["apps"], "resources": ["deployments"],
                     "verbs": ["get", "list", "watch", "create", "update", "patch"]},
                    {"apiGroups": [""], "resources": ["configmaps", "persistentvolumeclaims", "serviceaccounts"],
                     "verbs": ["get", "list", "watch", "create", "update", "patch"]},
                    {"apiGroups": ["networking.k8s.io"], "resources": ["networkpolicies"],
                     "verbs": ["get", "list", "watch", "create", "update", "patch"]}]},
            {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
                "metadata": {"name": "hmt-edge-reconciler", "namespace": ns},
                "subjects": [{"kind": "ServiceAccount", "name": "hmt-edge-reconciler", "namespace": ns}],
                "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "hmt-edge-reconciler"}}]},
    }
