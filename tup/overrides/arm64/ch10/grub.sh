#!/bin/bash
# OVERRIDE arm64/ch10/grub: the ESP is /dev/vdb1 DURING THE BUILD (the LFS disk
# is the build VM's second disk) and /dev/vda1 at final boot, so the mount
# here names vdb1 while grub.cfg names vda2. --removable installs to the
# EFI fallback path, so no NVRAM entry is needed anywhere.
set -e
mkdir -pv /boot/efi
mountpoint -q /boot/efi || mount /dev/vdb1 /boot/efi
grub-install --removable
cat > /boot/grub/grub.cfg << "GRUBEOF"
# Begin /boot/grub/grub.cfg — tup 0.1
set default=0
set timeout=5

insmod part_gpt
insmod ext2
set root=(hd0,2)

insmod efi_gop

menuentry "tup 0.1 (Linux 6.17.3)" {
        linux   /boot/vmlinuz-6.17.3-lfs-arm64-r12.4-42 root=/dev/vda2 ro console=ttyAMA0 net.ifnames=0
}
GRUBEOF
