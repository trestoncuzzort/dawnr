#!/bin/bash
# OVERRIDE arm64/ch10/fstab: the book's <xxx> placeholders, filled with tup's
# FINAL-BOOT device names: standalone under QEMU the disk is vda (inside the
# build VM it is vdb; that name never belongs in this file). No swap.
set -e
cat > /etc/fstab << "FSTABEOF"
# Begin /etc/fstab — tup 0.1

# file system  mount-point    type     options             dump  fsck
/dev/vda2      /              ext4     defaults            1     1
/dev/vda1      /boot/efi      vfat     umask=0077          0     2
proc           /proc          proc     nosuid,noexec,nodev 0     0
sysfs          /sys           sysfs    nosuid,noexec,nodev 0     0
devpts         /dev/pts       devpts   gid=5,mode=620      0     0
tmpfs          /run           tmpfs    defaults            0     0
devtmpfs       /dev           devtmpfs mode=0755,nosuid    0     0
tmpfs          /dev/shm       tmpfs    nosuid,nodev        0     0
cgroup2        /sys/fs/cgroup cgroup2  nosuid,noexec,nodev 0     0

# End /etc/fstab
FSTABEOF
