"""Device identities, immutable workloads and offline admission have negative tests."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from appliance_node import node_config
from appliance_workload import manifests

ROOT = Path(__file__).resolve().parents[1]


def identity() -> dict:
    return {"name": "forge-pi-01", "role": "server", "server": "https://192.168.1.10:6443",
            "token": "a" * 64, "ssh_key": "ssh-ed25519 " + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + b"A" * 32).decode()}


def test_unique_node_roles_and_private_server() -> None:
    value = identity()
    server = node_config(value)
    assert "server" not in server and "node-taint" in server
    assert server["node-name"] == "forge-pi-01"
    for name in ("forge-pi-02", "forge-pi-03"):
        agent = node_config({**value, "name": name, "role": "agent"})
        assert agent["server"] == value["server"] and "disable" not in agent


@pytest.mark.parametrize("field,value", [("name", "forge-pi-04"), ("name", "$(id)"), ("role", "agent"),
    ("token", "short"), ("token", "x" * 32 + "\n"), ("ssh_key", "no-key"), ("ssh_key", "ssh-ed25519 " + "A" * 68 + "\n"),
    ("server", "http://192.168.1.10:6443"), ("server", "https://user:pass@192.168.1.10:6443"),
    ("server", "https://192.168.1.10:443"), ("server", "https://192.168.1.10:6443/?x=y"), ("token", 123)])
def test_changed_or_injected_node_identity_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        node_config({**identity(), field: value})


def test_unknown_node_fields_are_rejected() -> None:
    with pytest.raises(ValueError):
        node_config({**identity(), "execute": "shell"})


def test_workload_has_one_writer_no_public_api_and_a_retained_ledger() -> None:
    image = "ghcr.io/collaborativemind/hmt-edge-robot-@sha256:" + "1" * 64
    items = {item["kind"]: item for item in manifests(ROOT, image)["items"]}
    spec = items["Deployment"]["spec"]
    assert spec["replicas"] == 1 and spec["strategy"]["type"] == "Recreate"
    pod = spec["template"]["spec"]
    assert pod["nodeSelector"]["kubernetes.io/hostname"] == "forge-pi-02"
    assert pod["containers"][0]["image"] == image
    assert pod["automountServiceAccountToken"] is False and pod["hostNetwork"] is False
    assert items["PersistentVolume"]["spec"]["persistentVolumeReclaimPolicy"] == "Retain"
    assert "Service" not in items and "Ingress" not in items
    assert "api_token" not in items["ConfigMap"]["data"]
    with pytest.raises(ValueError):
        manifests(ROOT, "ghcr.io/collaborativemind/hmt-edge-robot-:latest")
