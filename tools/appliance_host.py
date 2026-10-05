"""Install checksum-pinned official fixes only in a mounted disposable Pi image."""
from __future__ import annotations

import json
import platform
import re
import shutil
import sys
from pathlib import Path

from appliance_fetch import fetch
from appliance_process import run
from artifact_preflight import archive_hash
from ci_admission import ROOT


def packages(config: dict) -> list[dict]:
    result = config.get("packages")
    if not isinstance(result, list) or not 1 <= len(result) <= 32:
        raise ValueError("HOST_UPDATE_CATALOG_REQUIRED")
    names = set()
    for package in result:
        if not isinstance(package, dict) or set(package) != {"name", "version", "url", "sha256"}:
            raise ValueError("HOST_UPDATE_FIELDS")
        if not re.fullmatch(r"[a-z][a-z0-9+.-]{1,63}", package["name"]) or not re.fullmatch(r"[0-9][A-Za-z0-9.+:~\-]{0,99}", package["version"]):
            raise ValueError("HOST_UPDATE_IDENTITY")
        if package["name"] in names:
            raise ValueError("HOST_UPDATE_DUPLICATE")
        names.add(package["name"])
    return result


def fetch_updates(config: dict) -> None:
    destination = ROOT / "build/inputs/updates"
    destination.mkdir(parents=True, exist_ok=True)
    for package in packages(config):
        fetch({k: package[k] for k in ("url", "sha256")}, destination / (package["name"] + ".deb"))


def install(root: Path, config: dict) -> dict:
    if platform.machine() != "aarch64" or root.is_symlink() or root.resolve() != ROOT / "build/mount-root" or not root.is_mount():
        raise ValueError("HOST_UPDATE_DISPOSABLE_ARM64_MOUNT_REQUIRED")
    catalog = packages(config)
    destination = root / "usr/share/hmt/updates"
    destination.mkdir(parents=True, exist_ok=False)
    for package in catalog:
        source = ROOT / "build/inputs/updates" / (package["name"] + ".deb")
        if archive_hash(source) != package["sha256"]:
            raise ValueError("HOST_UPDATE_CHECKSUM_MISMATCH")
        fields = dict(line.split(": ", 1) for line in run(["/usr/bin/dpkg-deb", "--field", str(source)]).decode().splitlines() if ": " in line and not line.startswith(" "))
        if [fields.get(k) for k in ("Package", "Version", "Architecture")] != [package["name"], package["version"], "arm64"]:
            raise ValueError("HOST_UPDATE_PACKAGE_MISMATCH")
        shutil.copyfile(source, destination / source.name)
    policy = root / "usr/sbin/policy-rc.d"
    if policy.exists() or policy.is_symlink():
        raise ValueError("HOST_UPDATE_SERVICE_POLICY_EXISTS")
    policy.write_text("#!/bin/sh\nexit 101\n")
    policy.chmod(0o755)
    command = ["/usr/sbin/chroot", str(root)]
    try:
        print(run([*command, "/usr/bin/dpkg", "--install", *["/usr/share/hmt/updates/" + p["name"] + ".deb" for p in catalog]], timeout=300).decode())
        if run([*command, "/usr/bin/dpkg", "--audit"]).strip():
            raise ValueError("HOST_UPDATE_PACKAGE_AUDIT_FAILED")
    finally:
        policy.unlink(missing_ok=True)
    output = run([*command, "/usr/bin/dpkg-query", "--show", "--showformat=${Package}\t${Version}\t${Architecture}\n", *[p["name"] for p in catalog]])
    expected = {tuple(p[k] for k in ("name", "version")) + ("arm64",) for p in catalog}
    if {tuple(line.split("\t")) for line in output.decode().splitlines()} != expected:
        raise ValueError("HOST_UPDATE_READBACK_MISMATCH")
    report = {"status": "PASS", "scope": "OFFICIAL_HOST_PACKAGE_INSTALL_ONLY", "packages": catalog, "security_admission": "HOLD"}
    (root / "usr/share/hmt/host-updates.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.rmtree(destination)
    return report


if __name__ == "__main__":
    value = json.loads((ROOT / "deploy/appliance/inputs.json").read_text())
    if sys.argv[1:] == ["--fetch"]:
        fetch_updates(value)
    else:
        (ROOT / "build/host-updates.json").write_text('{"status":"FAIL","security_admission":"HOLD","reason":"HOST_UPDATE_NOT_COMPLETE"}\n')
        report = install(Path(sys.argv[1]), value)
        (ROOT / "build/host-updates.json").write_text(json.dumps(report, indent=2) + "\n")
