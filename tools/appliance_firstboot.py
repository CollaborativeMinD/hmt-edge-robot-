"""Provision on the Pi only; never provision identities during image construction."""
from __future__ import annotations

import json
import os
import pwd
import secrets
from pathlib import Path

from appliance_node import node_config
from appliance_process import run


def write(path: str, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(value)
    temporary.chmod(0o600)
    temporary.replace(target)


def main() -> None:
    boot = Path("/boot/firmware/hmt-node.json")
    saved = Path("/etc/hmt/node.json")
    value = json.loads((saved if saved.exists() else boot).read_text())
    config = node_config(value)
    write(str(saved), json.dumps(value))
    run(["/usr/bin/hostnamectl", "set-hostname", value["name"]])
    hosts = Path("/etc/hosts")
    hosts.write_text("\n".join(line for line in hosts.read_text().splitlines() if not line.startswith("127.0.1.1")) + "\n127.0.1.1 " + value["name"] + "\n")
    try:
        pwd.getpwnam("edgeadmin")
    except KeyError:
        run(["/usr/sbin/useradd", "--create-home", "--user-group", "--shell", "/bin/bash", "edgeadmin"])
    run(["/usr/sbin/usermod", "--password", "*", "edgeadmin"])
    write("/home/edgeadmin/.ssh/authorized_keys", value["ssh_key"] + "\n")
    run(["/usr/bin/chown", "-R", "edgeadmin:edgeadmin", "/home/edgeadmin/.ssh"])
    Path("/home/edgeadmin/.ssh").chmod(0o700)
    write("/etc/sudoers.d/hmt-edgeadmin", "edgeadmin ALL=(ALL) NOPASSWD: ALL\n")
    Path("/etc/sudoers.d/hmt-edgeadmin").chmod(0o440)
    write("/etc/ssh/sshd_config.d/hmt.conf", "PasswordAuthentication no\nPermitRootLogin no\n")
    run(["/usr/bin/ssh-keygen", "-A"])
    write("/etc/rancher/k3s/config.yaml", json.dumps(config))
    write("/etc/hmt/role", value["role"] + "\n")
    data = Path("/var/lib/hmt/ledger")
    data.mkdir(parents=True, exist_ok=True)
    os.chown(data, 10001, 10001)
    if value["role"] == "server" and not Path("/etc/hmt/runtime-secret.json").exists():
        write("/etc/hmt/runtime-secret.json", json.dumps({"apiVersion": "v1", "kind": "Secret",
            "metadata": {"name": "hmt-edge-runtime", "namespace": "hmt-edge-robot-sil"},
            "type": "Opaque", "stringData": {"api_token": secrets.token_hex(32), "operator_token": secrets.token_hex(32)}}))
    run(["/usr/bin/systemctl", "enable", "--now", "ssh"])
    boot.unlink(missing_ok=True)
    write("/etc/hmt/provisioned", value["name"] + "\n")


if __name__ == "__main__":
    main()
