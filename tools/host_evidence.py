"""Recompute host acceptance before signing; never extract untrusted tar paths."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path

from ci_admission import ROOT, digest
from host_policy import admit

NAMES = ('appliance-vulnerabilities', 'host-updates', 'host-hardening')


def assess(repo: Path, values: dict[str, bytes], commit: str) -> dict:
    policy_path = repo / 'policy/host_vulnerability_waivers.json'
    policy = json.loads(policy_path.read_text())
    if digest(repo / 'evidence/cd/host-risk/assessment.json') != policy['assessment_sha256']:
        raise ValueError('HOST_ASSESSMENT_CHANGED')
    scan, updates, hardened = (json.loads(values[name]) for name in NAMES)
    config = json.loads((repo / 'deploy/appliance/inputs.json').read_text())
    reduction = json.loads((repo / 'deploy/appliance/hardening.json').read_text())
    if updates.get('status') != 'PASS' or updates.get('packages') != config['packages'] or updates.get('scope') != 'OFFICIAL_HOST_PACKAGE_INSTALL_ONLY':
        raise ValueError('HOST_OFFICIAL_UPDATES_INCOMPLETE')
    if hardened.get('status') != 'PASS' or hardened.get('architecture') != 'arm64' or hardened.get('policy_sha256') != digest(repo / 'deploy/appliance/hardening.json'):
        raise ValueError('HOST_HARDENING_INCOMPLETE')
    if any(hardened.get(k) != reduction[k] for k in ('masked_services', 'blocked_modules')) or hardened.get('removed_packages') != reduction['remove_packages']:
        raise ValueError('HOST_MITIGATION_DRIFT')
    versions = {p['name']: p['version'] for p in hardened['packages']}
    if any(versions.get(p['name']) != p['version'] for p in config['packages'] if p['name'] not in reduction['remove_packages']):
        raise ValueError('HOST_UPDATE_INVENTORY_DRIFT')
    if versions.keys() & reduction['remove_packages'].keys():
        raise ValueError('HOST_REMOVED_PACKAGE_PRESENT')
    boot = hardened.get('boot', {})
    if boot.get('status') != 'PASS' or boot.get('module_policy') != 'most' or set(boot.get('images', {})) != {'v8', '2712'}:
        raise ValueError('HOST_BOOT_QUALIFICATION_INCOMPLETE')
    accepted = admit(scan, policy, hardened['packages'])
    return {'schema_version': 1, 'status': 'PASS', 'source_commit': commit,
        'scope': policy['scope'], 'architecture': 'arm64', 'disposition': policy['disposition'],
        'expires_at': policy['expires_at'], 'policy_sha256': digest(policy_path),
        'assessment_sha256': policy['assessment_sha256'],
        'image_sha256': digest(repo / 'build/hmt-edge-robot.img.xz') if (repo / 'build/hmt-edge-robot.img.xz').is_file() else None,
        'inputs': {name: hashlib.sha256(values[name]).hexdigest() for name in NAMES},
        'accepted_findings': accepted, 'accepted_count': len(accepted),
        'distinct_vulnerability_ids': len({x['vulnerability_id'] for x in accepted}), 'boot': boot}


def from_bundle(repo: Path, commit: str) -> dict:
    with tarfile.open(repo / 'build/evidence.tar.gz', 'r:gz') as bundle:
        names = [*(f'build/{name}.json' for name in NAMES), 'build/host-admission.json']
        values = {}
        for name in names:
            members = [m for m in bundle.getmembers() if m.name == name]
            if len(members) != 1 or not members[0].isfile() or members[0].size > 128 * 1024**2:
                raise ValueError('HOST_BUNDLE_MEMBER_INVALID')
            stream = bundle.extractfile(members[0])
            if stream is None:
                raise ValueError('HOST_BUNDLE_MEMBER_UNREADABLE')
            values[Path(name).stem] = stream.read()
    report = assess(repo, values, commit)
    if json.loads(values['host-admission']) != report:
        raise ValueError('HOST_RECEIPT_CHANGED_OR_STALE')
    return report


if __name__ == '__main__':
    commit = sys.argv[1] if len(sys.argv) == 2 else os.environ.get('GITHUB_SHA', '')
    output = ROOT / 'build/host-admission.json'
    output.write_text('{"status":"FAIL","reason":"HOST_ADMISSION_INCOMPLETE"}\n')
    values = {name: (ROOT / f'build/{name}.json').read_bytes() for name in NAMES}
    report = assess(ROOT, values, commit)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'accepted_findings'}))
