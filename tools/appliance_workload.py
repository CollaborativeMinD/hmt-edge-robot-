"""An independent SIL appliance profile; dormant stage-3 resources remain sealed."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

NS = "hmt-edge-robot-sil"


def manifests(root: Path, image: str) -> dict:
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("IMMUTABLE_GHCR_IMAGE_REQUIRED")
    source = root / "deploy/stage3/workload"
    workload = copy.deepcopy(json.loads((source / "workload.template.json").read_text()))
    workload["metadata"]["annotations"] = {"hmt.terminal-state.systems/profile": "appliance-sil"}
    workload["spec"]["replicas"] = 1
    pod = workload["spec"]["template"]["spec"]
    pod["nodeSelector"] = {"kubernetes.io/hostname": "forge-pi-02", "kubernetes.io/arch": "arm64", "kubernetes.io/os": "linux"}
    pod.pop("imagePullSecrets")
    container = pod["containers"][0]
    container["image"] = image
    container["readinessProbe"] = {"exec": {"command": ["python", "/etc/hmt/readiness.py"]},
                                    "timeoutSeconds": 5, "periodSeconds": 10, "failureThreshold": 3}
    policy = json.loads((source / "runtime-policy.json").read_text())
    policy["data"]["readiness.py"] = (root / "deploy/appliance/readiness.py").read_text()
    volume = {"apiVersion": "v1", "kind": "PersistentVolume", "metadata": {"name": "hmt-edge-ledger"},
        "spec": {"capacity": {"storage": "8Gi"}, "volumeMode": "Filesystem", "accessModes": ["ReadWriteOnce"],
        "persistentVolumeReclaimPolicy": "Retain", "storageClassName": "hmt-edge-local",
        "local": {"path": "/var/lib/hmt/ledger"}, "nodeAffinity": {"required": {"nodeSelectorTerms": [
        {"matchExpressions": [{"key": "kubernetes.io/hostname", "operator": "In", "values": ["forge-pi-02"]}]}]}}}}
    claim = {"apiVersion": "v1", "kind": "PersistentVolumeClaim",
        "metadata": {"name": "hmt-edge-ledger", "namespace": NS},
        "spec": {"accessModes": ["ReadWriteOnce"], "storageClassName": "hmt-edge-local",
                 "volumeName": "hmt-edge-ledger", "resources": {"requests": {"storage": "8Gi"}}}}
    account = json.loads((source / "serviceaccount.json").read_text())
    network = json.loads((source / "networkpolicy.json").read_text())
    return {"apiVersion": "v1", "kind": "List", "items": [volume, claim, account, policy, network, workload]}
