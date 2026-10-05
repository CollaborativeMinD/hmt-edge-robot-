"""Release signing never preserves stale success when fresh artifact admission fails."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest
from appliance_process import execute, run
from appliance_release import release
from host_evidence import assess as host_assess
from host_evidence import from_bundle


def test_failed_requalification_invalidates_old_signed_release(tmp_path: Path) -> None:
    directory = tmp_path / "build/release"
    directory.mkdir(parents=True)
    (directory / "release.json").write_text('{"status":"PASS"}')
    (directory / "release.sig").write_bytes(b"old")
    with pytest.raises(ValueError, match="OCI_ARCHIVE_UNAVAILABLE"):
        release(tmp_path, "1" * 40)
    assert not (directory / "release.sig").exists()
    assert '"FAIL"' in (directory / "release.json").read_text()


def test_appliance_process_reaps_timeout_and_rejects_failures() -> None:
    assert run(["/usr/bin/printf", "checked"]) == b"checked"
    with pytest.raises(ValueError, match="ABSOLUTE"):
        run(["printf", "unsafe-path"])
    with pytest.raises(subprocess.CalledProcessError):
        run(["/usr/bin/false"])
    with pytest.raises(TimeoutError):
        asyncio.run(execute(["/usr/bin/sleep", "2"], 1))


def test_firstboot_example_contains_no_real_credentials() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "deploy/appliance/node.example.json").read_text()
    assert "REPLACE_WITH" in text and "PRIVATE KEY" not in text
    assert os.environ.get("HMT_SIGNING_PRIVATE_KEY") is None


@pytest.mark.parametrize('tamper', ['receipt', 'commit', 'image', 'scan', 'none'])
def test_publisher_recomputes_host_receipt_and_image_binding(tmp_path: Path, tamper: str) -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ('policy/host_vulnerability_waivers.json', 'evidence/cd/host-risk/assessment.json'):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / name).read_bytes())
    policy = json.loads((tmp_path / 'policy/host_vulnerability_waivers.json').read_text())
    entry = policy['exceptions'][0]
    name, version = entry['package'], entry['installed_version']
    upstream, revision = version.rsplit('-', 1)
    epoch, upstream = (upstream.split(':', 1) if ':' in upstream else ('0', upstream))
    config = {'packages': [{'name': name, 'version': version}]}
    hardening = {'remove_packages': {}, 'masked_services': [], 'blocked_modules': []}
    path = tmp_path / 'deploy/appliance/hardening.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(hardening))
    (path.parent / 'inputs.json').write_text(json.dumps(config))
    hardened = {**hardening, 'removed_packages': {}, 'status': 'PASS', 'architecture': 'arm64',
        'policy_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'packages': [{'name': name, 'version': version, 'architecture': 'arm64'}],
        'boot': {'status': 'PASS', 'module_policy': 'most', 'images': {'v8': {}, '2712': {}}}}
    finding = dict(zip(('VulnerabilityID', 'PkgName', 'InstalledVersion', 'Severity'), entry.values(), strict=True))
    scan = {'SchemaVersion': 2, 'ArtifactType': 'filesystem', 'Metadata': {'OS': {'Family': 'debian', 'Name': '13.7'}},
        'Results': [{'Class': 'os-pkgs', 'Packages': [{'ID': name + '@' + version, 'Name': name, 'Version': upstream, 'Release': revision, 'Epoch': int(epoch), 'Arch': 'arm64'}], 'Vulnerabilities': [finding]}]}
    updates = {'status': 'PASS', 'scope': 'OFFICIAL_HOST_PACKAGE_INSTALL_ONLY', **config}
    values = {k: json.dumps(v).encode() for k, v in zip(('appliance-vulnerabilities', 'host-updates', 'host-hardening'), (scan, updates, hardened), strict=True)}
    build = tmp_path / 'build'
    build.mkdir()
    (build / 'hmt-edge-robot.img.xz').write_bytes(b'image')
    receipt = host_assess(tmp_path, values, '1' * 40)
    if tamper == 'receipt':
        receipt['accepted_count'] = 0
    if tamper == 'image':
        (build / 'hmt-edge-robot.img.xz').write_bytes(b'changed image')
    if tamper == 'scan':
        finding['FixedVersion'] = '999-1'
        values['appliance-vulnerabilities'] = json.dumps(scan).encode()
    values['host-admission'] = json.dumps(receipt).encode()
    with tarfile.open(build / 'evidence.tar.gz', 'w:gz') as bundle:
        for key, content in values.items():
            member = tarfile.TarInfo(f'build/{key}.json')
            member.size = len(content)
            bundle.addfile(member, io.BytesIO(content))
    if tamper == 'none':
        assert from_bundle(tmp_path, '1' * 40) == receipt
    else:
        with pytest.raises(ValueError):
            from_bundle(tmp_path, ('2' if tamper == 'commit' else '1') * 40)
