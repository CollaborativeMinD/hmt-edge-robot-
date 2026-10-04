"""Download only reviewed HTTPS assets; reject changed bytes before mounting."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from appliance_process import run
from artifact_preflight import archive_hash
from ci_admission import ROOT


def fetch(asset: dict, destination: Path) -> None:
    if set(asset) != {"url", "sha256"} or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
        raise ValueError("ASSET_CHECKSUM_REQUIRED")
    url = urlsplit(asset["url"])
    if url.scheme != "https" or url.hostname not in {"downloads.raspberrypi.com", "github.com"} or url.username or url.password:
        raise ValueError("ASSET_ORIGIN_NOT_ADMITTED")
    run(["/usr/bin/curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
                    "--retry", "3", "--max-time", "900", "--output", str(destination), asset["url"]], timeout=1000)
    if archive_hash(destination) != asset["sha256"]:
        destination.unlink()
        raise ValueError("ASSET_CHECKSUM_MISMATCH")


def main() -> None:
    config = json.loads((ROOT / "deploy/appliance/inputs.json").read_text())
    destination = ROOT / "build/inputs"
    destination.mkdir(parents=True, exist_ok=True)
    for asset, name in ((config["os"], "base.img.xz"), (config["k3s"]["binary"], "k3s-arm64"),
                        (config["k3s"]["airgap"], "k3s-airgap-images-arm64.tar.zst")):
        fetch(asset, destination / name)


if __name__ == "__main__":
    main()
