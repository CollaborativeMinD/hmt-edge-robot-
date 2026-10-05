#!/bin/bash
# Minimal device nodes and read-only kernel views for official offline maintscripts.
chroot_mounts() {
  local root="$1" boot="$2"
  mkdir -p "$root/dev" "$root/proc" "$root/sys" "$root/boot/firmware"
  mount -t tmpfs -o nosuid,noexec tmpfs "$root/dev"
  mknod -m 666 "$root/dev/null" c 1 3
  mknod -m 666 "$root/dev/zero" c 1 5
  mknod -m 666 "$root/dev/random" c 1 8
  mknod -m 666 "$root/dev/urandom" c 1 9
  mount -t proc -o ro,nosuid,nodev,noexec proc "$root/proc"
  mount --bind /sys "$root/sys"
  mount -o remount,bind,ro "$root/sys"
  mount --bind "$boot" "$root/boot/firmware"
}
chroot_unmounts() {
  local root="$1" directory
  for directory in boot/firmware sys proc dev; do
    if mountpoint -q "$root/$directory"; then umount "$root/$directory"; fi
  done
}
