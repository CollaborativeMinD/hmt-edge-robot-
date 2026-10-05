#!/bin/bash
# Native package-install qualification operates only on a newly copied image.
set -euo pipefail
[[ $(id -u) == 0 && $(uname -m) == aarch64 ]]
repo=$(realpath "$1")
work="$repo/build"
root="$work/mount-root"
loop=''
cleanup() {
  if mountpoint -q "$root"; then umount "$root"; fi
  if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
}
trap cleanup EXIT
mkdir -p "$root"
xz --decompress --stdout "$work/inputs/base.img.xz" > "$work/host-qualification.img"
loop=$(losetup --find --show --partscan "$work/host-qualification.img")
udevadm settle
[[ $(blkid -o value -s TYPE "${loop}p2") == ext4 ]]
mount "${loop}p2" "$root"
python3 "$repo/tools/appliance_host.py" "$root"
chroot "$root" /usr/bin/python3 -c 'import ssl; print(ssl.OPENSSL_VERSION)'
chroot "$root" /usr/bin/openssl version
