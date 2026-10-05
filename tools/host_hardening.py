"""Reduce only a disposable native Pi image with a reviewed removal closure."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

from appliance_process import run
from ci_admission import ROOT, digest

REQUIRED = {'systemd', 'udev', 'network-manager', 'wpasupplicant', 'rpi-swap', 'busybox',
    'initramfs-tools', 'dracut-install', 'raspi-firmware', 'openssh-server', 'openssh-client',
    'sudo', 'python3', 'linux-image-rpi-v8', 'linux-image-rpi-2712'}


def boot(root: Path, command: list[str]) -> dict:
    images = {}
    for flavour, name in (('v8', 'initramfs8'), ('2712', 'initramfs_2712')):
        paths = list((root / 'boot').glob(f'initrd.img-*-rpi-{flavour}'))
        if len(paths) != 1 or digest(paths[0]) != digest(root / 'boot/firmware' / name):
            raise ValueError('HOST_BOOT_PARTITION_INITRAMFS_MISMATCH')
        listing = run([*command, '/usr/bin/lsinitramfs', '/boot/' + paths[0].name], timeout=60).decode()
        if not any(line.endswith('etc/modprobe.d/90-hmt-restricted.conf') for line in listing.splitlines()):
            raise ValueError('HOST_INITRAMFS_MITIGATION_MISSING')
        version = paths[0].name.removeprefix('initrd.img-')
        config = root / 'boot' / ('config-' + version)
        if any(f'{option}=y' not in config.read_text().splitlines() for option in ('CONFIG_EXT4_FS', 'CONFIG_MMC', 'CONFIG_MMC_SDHCI', 'CONFIG_MMC_BCM2835')):
            raise ValueError('HOST_PI_BOOT_DRIVER_MISSING')
        images[flavour] = {'kernel': version, 'initramfs_sha256': digest(paths[0]), 'config_sha256': digest(config)}
    return {'status': 'PASS', 'module_policy': 'most', 'images': images}


def reduce(root: Path, repo: Path = ROOT) -> dict:
    if platform.machine() != 'aarch64' or root.is_symlink() or root.resolve() != repo / 'build/mount-root' or not root.is_mount():
        raise ValueError('HOST_REDUCTION_DISPOSABLE_ARM64_REQUIRED')
    path = repo / 'deploy/appliance/hardening.json'
    policy = json.loads(path.read_text())
    removals = policy['remove_packages']
    command = ['/usr/sbin/chroot', str(root)]
    output = run([*command, '/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Version}\t${Essential}\n', *removals]).decode()
    actual = {line.split('\t')[0]: line.split('\t')[1] for line in output.splitlines()}
    if actual != removals or any(line.endswith('\tyes') for line in output.splitlines()) or REQUIRED & removals.keys():
        raise ValueError('HOST_REDUCTION_PACKAGE_DRIFT_OR_ESSENTIAL')
    for unit in policy['masked_services']:
        target = root / 'etc/systemd/system' / unit
        target.unlink(missing_ok=True)
        target.symlink_to('/dev/null')
    text = ''.join(f'install {name} /bin/false\nblacklist {name}\n' for name in policy['blocked_modules'])
    (root / 'etc/modprobe.d/90-hmt-restricted.conf').write_text(text)
    for name in ('mount', 'umount'):
        file = root / 'usr/bin' / name
        file.chmod(file.stat().st_mode & 0o1777)
    ssh = 'PasswordAuthentication no\nPermitRootLogin no\nAllowUsers edgeadmin\nGSSAPIAuthentication no\nDisableForwarding yes\nPermitTunnel no\n'
    (root / 'etc/ssh/sshd_config.d/00-hmt-hardening.conf').write_text(ssh)
    (root / 'etc/initramfs-tools/conf.d/99-hmt-portable').write_text('MODULES=most\n')
    guard = root / 'usr/sbin/policy-rc.d'
    if guard.exists() or guard.is_symlink():
        raise ValueError('HOST_REDUCTION_SERVICE_POLICY_EXISTS')
    guard.write_text('#!/bin/sh\nexit 101\n')
    guard.chmod(0o755)
    try:
        print(run([*command, '/usr/bin/dpkg', '--purge', *removals], timeout=300).decode())
        if run([*command, '/usr/bin/dpkg', '--audit']).strip():
            raise ValueError('HOST_REDUCTION_AUDIT_FAILED')
    except subprocess.CalledProcessError as error:
        print((error.output or b'').decode(errors='replace'))
        print((error.stderr or b'').decode(errors='replace'), file=sys.stderr)
        raise
    finally:
        guard.unlink(missing_ok=True)
    inventory = run([*command, '/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n']).decode()
    packages = [dict(zip(('name', 'version', 'architecture'), line.split('\t')[:3], strict=True)) for line in inventory.splitlines() if line.endswith('\tinstalled')]
    names = {p['name'] for p in packages}
    if not REQUIRED <= names or names & removals.keys() or any(p['architecture'] not in ('all', 'arm64') for p in packages):
        raise ValueError('HOST_REDUCTION_READBACK_FAILED')
    report = {'status': 'PASS', 'scope': policy['scope'], 'architecture': 'arm64',
        'policy_sha256': digest(path), 'removed_packages': removals, 'packages': packages,
        'masked_services': policy['masked_services'], 'blocked_modules': policy['blocked_modules'],
        'boot': boot(root, command)}
    (root / 'usr/share/hmt/host-hardening.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    output = ROOT / 'build/host-hardening.json'
    output.write_text('{"status":"FAIL","reason":"HOST_REDUCTION_INCOMPLETE"}\n')
    output.write_text(json.dumps(reduce(Path(sys.argv[1])), indent=2) + '\n')
