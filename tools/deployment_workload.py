"""Dormant SIL pod template with explicit unimplemented readiness."""

from __future__ import annotations

from typing import Any

from deployment_contracts import DeploymentPlan

LABELS = {"app.kubernetes.io/name": "hmt-edge-robot"}
UNBUILT_IMAGE = "{{QUALIFIED_IMAGE_DIGEST_REQUIRED}}"


def workload(plan: DeploymentPlan) -> dict[str, Any]:
    resource = plan.resources
    probe = {"exec": {"command": ["python", "-c",
             "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).close()"]},
             "timeoutSeconds": 3, "periodSeconds": 10, "failureThreshold": 3}
    env = [{"name": name, "valueFrom": {"secretKeyRef": {"name": secret, "key": key}}}
           for name, secret, key in (("HMT_API_TOKEN", plan.api_secret, "api_token"),
                                    ("HMT_OPERATOR_TOKEN", plan.operator_secret, "operator_token"))]
    env.append({"name": "TMPDIR", "value": "/run/hmt-scratch"})
    container = {"name": "supervisor", "image": UNBUILT_IMAGE, "imagePullPolicy": "IfNotPresent",
        "command": ["hmt-edge-robot"],
        "args": ["serve", "--database", "/data/cell.db", "--policy", "/etc/hmt/runtime-policy.json"],
        "env": env, "securityContext": {"allowPrivilegeEscalation": False,
        "privileged": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
        "resources": {"requests": {"cpu": f"{resource.request_cpu_m}m", "memory": f"{resource.request_memory_mib}Mi"},
                      "limits": {"cpu": f"{resource.limit_cpu_m}m", "memory": f"{resource.limit_memory_mib}Mi"}},
        "startupProbe": {**probe, "failureThreshold": 12}, "livenessProbe": probe,
        "readinessProbe": {"exec": {"command": ["python", "-c", "raise SystemExit(1)"]},
                           "timeoutSeconds": 1, "periodSeconds": 10},
        "volumeMounts": [{"name": "ledger", "mountPath": "/data"},
                         {"name": "policy", "mountPath": "/etc/hmt", "readOnly": True},
                         {"name": "scratch", "mountPath": "/run/hmt-scratch"}]}
    pod = {"serviceAccountName": "hmt-edge-runtime", "automountServiceAccountToken": False,
        "hostNetwork": False, "hostPID": False, "hostIPC": False,
        "nodeSelector": {"kubernetes.io/os": "linux", "kubernetes.io/arch": "arm64",
                         "hmt.terminal-state.systems/owner": plan.node_owner},
        "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001,
                            "fsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
        "imagePullSecrets": [{"name": plan.registry_secret}], "terminationGracePeriodSeconds": 30,
        "containers": [container], "volumes": [
            {"name": "ledger", "persistentVolumeClaim": {"claimName": "hmt-edge-ledger"}},
            {"name": "policy", "configMap": {"name": "hmt-edge-runtime-policy"}},
            {"name": "scratch", "emptyDir": {"sizeLimit": "64Mi"}}]}
    return {"apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": "hmt-edge-robot", "namespace": plan.namespace,
                     "annotations": {"hmt.terminal-state.systems/admission": "HOLD"}},
        "spec": {"replicas": plan.replicas, "strategy": {"type": "Recreate"},
                 "selector": {"matchLabels": LABELS},
                 "template": {"metadata": {"labels": LABELS}, "spec": pod}}}
