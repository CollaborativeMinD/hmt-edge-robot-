"""Validate per-device identity; boot data never becomes executable shell code."""
from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlsplit

NODES = {"forge-pi-01": "server", "forge-pi-02": "agent", "forge-pi-03": "agent"}


def node_config(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != {"name", "role", "server", "token", "ssh_key"}:
        raise ValueError("NODE_CONFIG_FIELDS")
    if any(not isinstance(v, str) for v in value.values()):
        raise ValueError("NODE_CONFIG_TYPES")
    if NODES.get(value["name"]) != value["role"]:
        raise ValueError("NODE_OWNER_OR_ROLE")
    if not re.fullmatch(r"[A-Za-z0-9:._-]{32,512}", value["token"]):
        raise ValueError("NODE_TOKEN_INVALID")
    key = value["ssh_key"]
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/=]{40,100}( [^\r\n]{1,100})?", key):
        raise ValueError("SSH_KEY_REQUIRED")
    decoded = base64.b64decode(key.split()[1], validate=True)
    if len(decoded) != 51 or decoded[:19] != b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20":
        raise ValueError("SSH_KEY_INVALID")
    url = urlsplit(value["server"])
    if url.scheme != "https" or not url.hostname or url.port != 6443 or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError("PRIVATE_SERVER_URL_REQUIRED")
    result = {"node-name": value["name"], "token": value["token"], "write-kubeconfig-mode": "0600", "kubelet-arg": ["fail-swap-on=false"]}
    if value["role"] == "server":
        result.update({"disable": ["traefik", "servicelb", "metrics-server"],
                       "tls-san": [url.hostname], "node-taint": ["node-role.kubernetes.io/control-plane=true:NoSchedule"]})
    else:
        result["server"] = value["server"]
    return result
