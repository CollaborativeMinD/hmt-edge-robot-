#!/bin/bash
# Native package-install qualification operates only on a newly copied image.
set -euo pipefail
[[ $(id -u) == 0 && $(uname -m) == aarch64 ]]
repo=$(realpath "$1")
work="$repo/build"
root="$work/mount-root"
boot="$work/mount-boot"
loop=''
# shellcheck source=chroot-mounts.sh
source "$repo/deploy/appliance/chroot-mounts.sh"
cleanup() {
  chroot_unmounts "$root"
  if mountpoint -q "$boot"; then umount "$boot"; fi
  if mountpoint -q "$root"; then umount "$root"; fi
  if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
}
trap cleanup EXIT
mkdir -p "$root" "$boot"
xz --decompress --stdout "$work/inputs/base.img.xz" > "$work/host-qualification.img"
loop=$(losetup --find --show --partscan "$work/host-qualification.img")
udevadm settle
[[ $(blkid -o value -s TYPE "${loop}p2") == ext4 ]]
mount "${loop}p2" "$root"
mount "${loop}p1" "$boot"
chroot_mounts "$root" "$boot"
python3 "$repo/tools/appliance_host.py" "$root"
python3 "$repo/tools/host_hardening.py" "$root"
chroot "$root" /usr/bin/python3 -c 'import ssl; print(ssl.OPENSSL_VERSION)'
chroot "$root" /usr/bin/openssl version
chroot_unmounts "$root"
trivy=aquasec/trivy:0.69.3
docker pull "$trivy"
trivy=$(docker image inspect "$trivy" --format '{{index .RepoDigests 0}}')
docker run --rm --mount "type=bind,src=$root,dst=/scan,readonly" --mount "type=bind,src=$work,dst=/out" \
  "$trivy" rootfs --scanners vuln,secret --list-all-pkgs --format json --output /out/appliance-vulnerabilities.json --timeout 10m /scan
python3 "$repo/tools/host_evidence.py" "$GITHUB_SHA"
