#!/bin/bash
# Operates exclusively on a newly created image file on a disposable hosted runner.
set -euo pipefail
[[ $(id -u) == 0 && $(uname -m) == aarch64 ]]
repo=$(realpath "$1")
work="$repo/build"
image="$work/hmt-edge-robot.img"
root="$work/mount-root"
boot="$work/mount-boot"
loop=''
cleanup() {
  mountpoint -q "$boot" && umount "$boot"
  mountpoint -q "$root" && umount "$root"
  if [[ -n "$loop" ]]; then losetup -d "$loop"; fi
}
trap cleanup EXIT
mkdir -p "$root" "$boot"
xz --decompress --stdout "$work/inputs/base.img.xz" > "$image"
size=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_size_gib"])' "$repo/deploy/appliance/inputs.json")
[[ "$size" =~ ^[0-9]+$ && "$size" -ge 8 && "$size" -le 16 ]]
truncate -s "${size}G" "$image"
parted --script "$image" resizepart 2 100%
loop=$(losetup --find --show --partscan "$image")
udevadm settle
[[ $(blkid -o value -s TYPE "${loop}p1") == vfat ]]
[[ $(blkid -o value -s TYPE "${loop}p2") == ext4 ]]
e2fsck -fy "${loop}p2" || [[ $? == 1 ]]
resize2fs "${loop}p2"
mount "${loop}p2" "$root"
mount "${loop}p1" "$boot"
[[ -f "$root/usr/lib/systemd/systemd" && -f "$root/usr/bin/python3" ]]
python3 "$repo/tools/appliance_host.py" "$root"
python3 "$repo/tools/host_hardening.py" "$root"
install -Dm755 "$work/inputs/k3s-arm64" "$root/usr/local/bin/k3s"
install -Dm755 "$repo/deploy/appliance/k3s-start.sh" "$root/usr/local/libexec/hmt-k3s-start"
install -Dm755 "$repo/deploy/appliance/runtime-start.sh" "$root/usr/local/libexec/hmt-runtime-start"
install -Dm644 "$repo/tools/appliance_firstboot.py" "$root/usr/local/libexec/hmt-firstboot.py"
install -Dm644 "$repo/tools/appliance_node.py" "$root/usr/local/libexec/appliance_node.py"
install -Dm644 "$repo/tools/appliance_process.py" "$root/usr/local/libexec/appliance_process.py"
mkdir -p "$root/usr/share/hmt" "$root/etc/systemd/system/multi-user.target.wants" "$root/var/lib/rancher/k3s/agent/images"
cp "$work/payload/"* "$root/usr/share/hmt/"
cp "$work/inputs/k3s-airgap-images-arm64.tar.zst" "$root/var/lib/rancher/k3s/agent/images/"
for unit in k3s hmt-firstboot hmt-runtime; do
  install -m644 "$repo/deploy/appliance/$unit.service" "$root/etc/systemd/system/$unit.service"
  ln -sf "/etc/systemd/system/$unit.service" "$root/etc/systemd/system/multi-user.target.wants/$unit.service"
done
# This appliance owns provisioning; do not run the vendor interactive user dialog
# or cloud-init metadata alongside its identity and credential setup.
mkdir -p "$root/etc/cloud"
touch "$root/etc/cloud/cloud-init.disabled"
ln -sf /dev/null "$root/etc/systemd/system/userconfig.service"
# Rootfs expansion remains in the vendor boot path. Add memory cgroups for k3s.
python3 - "$boot/cmdline.txt" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
args = p.read_text().strip().split()
for option in ('cgroup_enable=cpuset', 'cgroup_enable=memory', 'cgroup_memory=1'):
    if option not in args:
        args.append(option)
p.write_text(' '.join(args) + '\n')
PY
printf 'br_netfilter\noverlay\n' > "$root/etc/modules-load.d/hmt.conf"
printf 'net.ipv4.ip_forward=1\nnet.bridge.bridge-nf-call-iptables=1\n' > "$root/etc/sysctl.d/90-hmt.conf"
# Empty identities cause systemd/sshd to generate unique values on each device.
: > "$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id" "$root/var/lib/systemd/random-seed" "$root/etc/ssh/ssh_host_"*
ln -s /etc/machine-id "$root/var/lib/dbus/machine-id"
cp "$repo/deploy/appliance/node.example.json" "$boot/hmt-node.example.json"
sync
trivy=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["trivy"])' "$repo/evidence/cd/stage4/base-lock.json")
docker run --rm --mount "type=bind,src=$root,dst=/scan,readonly" --mount "type=bind,src=$work,dst=/out" \
  "$trivy" rootfs --scanners vuln,secret --list-all-pkgs --format json --output /out/appliance-vulnerabilities.json --timeout 10m /scan
python3 "$repo/tools/host_evidence.py" "$GITHUB_SHA"
cleanup
loop=''
trap - EXIT
xz --threads=2 -1 --keep "$image"
chmod 644 "$image.xz"
python3 "$repo/tools/host_evidence.py" "$GITHUB_SHA"
