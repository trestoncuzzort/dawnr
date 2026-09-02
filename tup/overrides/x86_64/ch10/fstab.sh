#!/bin/bash
# OVERRIDE x86_64/ch10/fstab: the book's <xxx>/<fff> placeholders, filled
# with tup's FINAL-BOOT device names. Standalone under QEMU the disk is vda
# and its single partition is the root (inside the build VM it is vdb1; that
# name never belongs in this file). No swap partition (the book's <yyy> line
# is dropped, not filled). No ESP: the x86 leg boots BIOS GRUB from the MBR,
# which is why this file differs from arm64/ch10/fstab.sh.
set -e
cat > /etc/fstab << "FSTABEOF"
# Begin /etc/fstab (tup 0.1, x86_64)

# file system  mount-point    type     options             dump  fsck
/dev/vda1      /              ext4     defaults            1     1
proc           /proc          proc     nosuid,noexec,nodev 0     0
sysfs          /sys           sysfs    nosuid,noexec,nodev 0     0
devpts         /dev/pts       devpts   gid=5,mode=620      0     0
tmpfs          /run           tmpfs    defaults            0     0
devtmpfs       /dev           devtmpfs mode=0755,nosuid    0     0
tmpfs          /dev/shm       tmpfs    nosuid,nodev        0     0
cgroup2        /sys/fs/cgroup cgroup2  nosuid,noexec,nodev 0     0

# End /etc/fstab
FSTABEOF
