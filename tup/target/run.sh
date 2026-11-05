#!/bin/bash
# Called only by build.py inside new mount, network, PID and UTS namespaces.
# Runs the named layer chapters with the unchanged driver in a chroot of the
# export, then revalidates each chapter. Nothing outside the export is written.
set -euo pipefail
[ "$#" -ge 7 ] || exit 2
root=$1 jobs=$2 parent_netns=$3 parent_mnt=$4 parent_pid=$5 parent_uts=$6
shift 6
chapters=("$@")
[[ $root = /* && $root != / && $jobs =~ ^[1-4]$ ]] || exit 2
[ "$(readlink -f -- "$root")" = "$root" ] || exit 2
[ "$(readlink /proc/self/ns/net)" != "$parent_netns" ] || exit 2
[ "$(readlink /proc/self/ns/mnt)" != "$parent_mnt" ] || exit 2
[ "$(readlink /proc/self/ns/pid)" != "$parent_pid" ] || exit 2
[ "$(readlink /proc/self/ns/uts)" != "$parent_uts" ] || exit 2
for chapter in "${chapters[@]}"; do
  [[ $chapter =~ ^[a-z][a-z0-9-]*$ ]] && [ -s "$root/tup-layer/chapters/$chapter/ORDER" ] || exit 2
done
[ -s "$root/tup-layer/driver.sh" ] && [ -s "$root/tup-layer/common.sh" ] || exit 2
mount --make-rprivate /
# Make the export a mount point of this namespace: test code inside the chroot
# (the firewall probe) creates further namespaces and must be able to change
# the propagation of its own root. https://man7.org/linux/man-pages/man1/unshare.1.html
mount --bind "$root" "$root"
for name in dev proc sys run tmp; do
  [ ! -L "$root/$name" ] || exit 2
  # The export omits these directories; recreate them with their final modes.
  [ -d "$root/$name" ] || install -d -m "$([ "$name" = tmp ] && echo 1777 || echo 0755)" "$root/$name"
  mountpoint -q "$root/$name" && exit 2
done
# Minimal disposable devices: no host block device or host /run is exposed.
mount -t tmpfs -o nosuid,mode=0755 tmpfs "$root/dev"
for item in 'null 1 3' 'zero 1 5' 'full 1 7' 'random 1 8' 'urandom 1 9' 'tty 5 0'; do
  read -r name major minor <<< "$item"
  mknod -m 0666 "$root/dev/$name" c "$major" "$minor"
done
mkdir -p "$root/dev/pts" "$root/dev/shm"
mount -t devpts -o newinstance,gid=5,mode=0620,ptmxmode=0666 devpts "$root/dev/pts"
ln -s pts/ptmx "$root/dev/ptmx"
ln -s /proc/self/fd "$root/dev/fd"
ln -s /proc/self/fd/0 "$root/dev/stdin"
ln -s /proc/self/fd/1 "$root/dev/stdout"
ln -s /proc/self/fd/2 "$root/dev/stderr"
mount -t tmpfs -o nosuid,nodev,mode=1777 tmpfs "$root/dev/shm"
mount -t proc proc "$root/proc"
mount -t sysfs -o ro sysfs "$root/sys"
mount -t tmpfs -o nosuid,nodev tmpfs "$root/run"
# Package suites leave sockets and scratch files here; none may reach the image.
mount -t tmpfs -o nosuid,nodev,mode=1777 tmpfs "$root/tmp"
hostname tup-build
[ -f "$root/etc/hosts" ] && [ ! -L "$root/etc/hosts" ] || exit 2
cat "$root/etc/hosts" > "$root/run/hosts"
printf '127.0.1.1 tup-build\n' >> "$root/run/hosts"
mount --bind "$root/run/hosts" "$root/etc/hosts"
ip link set lo up
common=(HOME=/root TERM=dumb PATH=/usr/bin:/usr/sbin LFS= LC_ALL=POSIX LANG=POSIX TZ=UTC
  TUP_ARCH=x86_64 TUP_PROFILE=native-x86_64-lfs-13.1-systemd-layers
  TUP_TESTS='libnftnl nftables openssh sudo' TUP_JOBS="$jobs" MAKEFLAGS="-j$jobs"
  PYTHONDONTWRITEBYTECODE=1 TUP_LAYER_CHROOT=1 TUP_LAYER_PARENT_NETNS="$parent_netns"
  TUP_OVERRIDES=/tup-layer/overrides TUP_BUILD_INPUTS=/tup-layer/BUILD-INPUTS.json)
for chapter in "${chapters[@]}"; do
  chroot "$root" /usr/bin/env -i "${common[@]}" \
    /bin/bash /tup-layer/driver.sh "/tup-layer/chapters/$chapter" < /dev/null
done
for chapter in "${chapters[@]}"; do
  chroot "$root" /usr/bin/env -i "${common[@]}" TUP_VALIDATE_ONLY=1 \
    /bin/bash /tup-layer/driver.sh "/tup-layer/chapters/$chapter" < /dev/null
done
