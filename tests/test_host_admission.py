"""Host risk acceptance cannot admit changed findings or substituted release evidence."""
from __future__ import annotations

import copy
import json
import tarfile
from datetime import date
from pathlib import Path

import pytest
from host_evidence import from_bundle
from host_policy import FIELDS, admit, validate

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> tuple[dict, dict, list[dict]]:
    policy = json.loads((ROOT / 'policy/host_vulnerability_waivers.json').read_text())
    entry = policy['exceptions'][0]
    name, version = entry['package'], entry['installed_version']
    upstream, release = version.rsplit('-', 1)
    inventory = [{'name': name, 'version': version, 'architecture': 'arm64'}]
    finding = dict(zip(('VulnerabilityID', 'PkgName', 'InstalledVersion', 'Severity'), (entry[k] for k in FIELDS), strict=True))
    scan = {'SchemaVersion': 2, 'ArtifactType': 'filesystem', 'Metadata': {'OS': {'Family': 'debian', 'Name': '13.7'}},
        'Results': [{'Class': 'os-pkgs', 'Packages': [{'Name': name, 'Version': upstream, 'Release': release, 'Arch': 'arm64'}], 'Vulnerabilities': [finding]}]}
    return scan, policy, inventory


def test_exact_host_acceptance_retains_raw_severity_and_identity() -> None:
    scan, policy, inventory = fixture()
    before = copy.deepcopy(scan)
    assert admit(scan, policy, inventory) == [policy['exceptions'][0]]
    assert scan == before


@pytest.mark.parametrize('change', [{'VulnerabilityID': 'CVE-2099-12345'}, {'InstalledVersion': '999-1'},
    {'Severity': 'CRITICAL'}, {'FixedVersion': '999-1'}, {'PkgName': 'unreviewed'}])
def test_unreviewed_or_fixed_host_findings_fail(change: dict) -> None:
    scan, policy, inventory = fixture()
    original = scan['Results'][0]['Vulnerabilities'][0]
    if change.get('Severity') == original['Severity']:
        change = {'Severity': 'UNKNOWN'}
    original.update(change)
    with pytest.raises(ValueError, match='NOT_ADMITTED'):
        admit(scan, policy, inventory)


@pytest.mark.parametrize('kind', ['secret', 'arch', 'os', 'container', 'inventory', 'language'])
def test_waiver_scope_and_complete_inventory_are_enforced(kind: str) -> None:
    scan, policy, inventory = fixture()
    if kind == 'secret':
        scan['Results'][0]['Secrets'] = [{'Finding': 'secret'}]
    if kind == 'arch':
        inventory[0]['architecture'] = 'amd64'
    if kind == 'os':
        scan['Metadata']['OS']['Name'] = '12'
    if kind == 'container':
        scan['ArtifactType'] = 'container_image'
    if kind == 'inventory':
        scan['Results'][0]['Packages'] = []
    if kind == 'language':
        scan['Results'][0]['Class'] = 'lang-pkgs'
    with pytest.raises(ValueError):
        admit(scan, policy, inventory)


def test_expiry_duplicates_and_wildcards_are_rejected() -> None:
    _, policy, _ = fixture()
    with pytest.raises(ValueError, match='EXPIRED'):
        validate(policy, date(2027, 1, 4))
    policy['exceptions'].append(policy['exceptions'][0])
    with pytest.raises(ValueError, match='DUPLICATE'):
        validate(policy)
    policy['exceptions'][0]['package'] = '*'
    with pytest.raises(ValueError, match='IDENTITY'):
        validate(policy)


def test_bundle_rejects_duplicate_members_without_extracting(tmp_path: Path) -> None:
    directory = tmp_path / 'build'
    directory.mkdir()
    source = directory / 'appliance-vulnerabilities.json'
    source.write_text('{}')
    with tarfile.open(directory / 'evidence.tar.gz', 'w:gz') as bundle:
        bundle.add(source, arcname='build/appliance-vulnerabilities.json')
        bundle.add(source, arcname='build/appliance-vulnerabilities.json')
    with pytest.raises(ValueError, match='MEMBER_INVALID'):
        from_bundle(tmp_path, '1' * 40)
