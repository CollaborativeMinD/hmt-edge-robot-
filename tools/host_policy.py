"""Validate explicit, expiring owner acceptance of assessed host findings."""
from __future__ import annotations

from datetime import date

FIELDS = ('vulnerability_id', 'package', 'installed_version', 'severity')


def identity(value: dict) -> tuple[str, ...]:
    if set(value) != set(FIELDS) or any(not isinstance(value[k], str) or not value[k] or '*' in value[k] for k in FIELDS):
        raise ValueError('HOST_WAIVER_IDENTITY_INVALID')
    if value['severity'] not in ('HIGH', 'CRITICAL', 'UNKNOWN'):
        raise ValueError('HOST_WAIVER_SEVERITY_INVALID')
    return tuple(value[k] for k in FIELDS)


def validate(policy: dict, today: date | None = None) -> set[tuple[str, ...]]:
    fields = {'schema_version', 'scope', 'approved_by', 'approved_at', 'expires_at',
        'approval_reference', 'disposition', 'assessment_sha256', 'exceptions'}
    if set(policy) != fields or type(policy['schema_version']) is not int or policy['schema_version'] != 1:
        raise ValueError('HOST_WAIVER_SCHEMA_INVALID')
    if policy['scope'] != 'PI_ARM64_DEBIAN13_HOST_ONLY' or policy['approved_by'] != 'repository_owner' or policy['disposition'] != 'OWNER_ACCEPTED_RISK_NOT_FIXED':
        raise ValueError('HOST_WAIVER_AUTHORITY_INVALID')
    approved, expires = date.fromisoformat(policy['approved_at']), date.fromisoformat(policy['expires_at'])
    if not approved <= (today or date.today()) <= expires or not 0 < (expires - approved).days <= 90 or not policy['approval_reference'].strip():
        raise ValueError('HOST_WAIVER_EXPIRED_OR_UNAPPROVED')
    exceptions = policy['exceptions']
    if not isinstance(exceptions, list) or not 1 <= len(exceptions) <= 2048:
        raise ValueError('HOST_WAIVER_CATALOG_INVALID')
    identities = {identity(x) for x in exceptions}
    if len(identities) != len(exceptions):
        raise ValueError('HOST_WAIVER_DUPLICATE')
    return identities


def package_identity(package: dict) -> tuple[str, str, str]:
    epoch = package.get('Epoch', 0)
    if type(epoch) is not int or epoch < 0:
        raise ValueError('HOST_SCAN_EPOCH_INVALID')
    version = (str(epoch) + ':' if epoch else '') + package['Version']
    if package.get('Release'):
        version += '-' + package['Release']
    if package.get('ID') != package['Name'] + '@' + version:
        raise ValueError('HOST_SCAN_PACKAGE_ID_INVALID')
    return package['Name'], version, package['Arch']


def admit(scan: dict, policy: dict, inventory: list[dict]) -> list[dict]:
    allowed = validate(policy)
    os = scan.get('Metadata', {}).get('OS', {})
    results = scan.get('Results', [])
    if scan.get('SchemaVersion') != 2 or scan.get('ArtifactType') != 'filesystem' or os.get('Family') != 'debian' or os.get('Name', '').split('.')[0] != '13':
        raise ValueError('HOST_SCAN_SCOPE_INVALID')
    expected = {(p['name'], p['version'], p['architecture']) for p in inventory}
    packages = [p for r in results if r.get('Class') == 'os-pkgs' for p in r.get('Packages', [])]
    actual = {package_identity(p) for p in packages}
    if not expected or expected != actual or any(p[2] not in ('arm64', 'all') for p in expected):
        raise ValueError('HOST_SCAN_INVENTORY_MISMATCH')
    accepted = []
    for result in results:
        if result.get('Secrets'):
            raise ValueError('HOST_SECRET_DETECTED')
        for finding in result.get('Vulnerabilities') or []:
            if finding.get('Severity') in ('LOW', 'MEDIUM'):
                continue
            entry = dict(zip(FIELDS, (finding.get(k) for k in ('VulnerabilityID', 'PkgName', 'InstalledVersion', 'Severity')), strict=True))
            if result.get('Class') != 'os-pkgs' or finding.get('FixedVersion') or identity(entry) not in allowed:
                raise ValueError('HOST_FINDING_NOT_ADMITTED')
            accepted.append(entry)
    return accepted
