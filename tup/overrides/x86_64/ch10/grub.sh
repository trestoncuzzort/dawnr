#!/bin/bash
# OVERRIDE x86_64/ch10/grub: BIOS GRUB (i386-pc), which is the x86 book's own
# route; the ruling and its reasons are in X86-FEASIBILITY.md. Two things
# the page leaves to the reader are filled here:
#   - the disk. The page says /dev/sda. DURING THE BUILD the LFS disk is the
#     build VM's second virtio disk, /dev/vdb (one partition, vdb1 = /), and
#     at final boot it is the only disk, /dev/vda. grub-install names vdb;
#     grub.cfg names vda1. --target=i386-pc is stated because the page notes
#     grub-install guesses x86_64-efi on a UEFI-booted host.
#   - grub.cfg: the page's own file with its placeholders filled. root is
#     (hd0,1) on an MBR label (part_msdos, not part_gpt); the kernel name is
#     read off the page rather than typed; console=ttyS0 makes the boot
#     witness visible on the serial port; net.ifnames=0 keeps eth0 the name
#     the ch09 network override configured.
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the grub page"; exit 1; }
KERNEL=$(sed -n 's@^ *linux *\(/boot/vmlinuz-[^ ]*\) .*@\1@p' "$PAGE" | head -1)
[ -n "$KERNEL" ] || { echo "override: no vmlinuz name on the grub page"; exit 1; }
[ -f "$KERNEL" ] || { echo "override: $KERNEL is not installed; the kernel page did not run"; exit 1; }
grub-install --target=i386-pc /dev/vdb
cat > /boot/grub/grub.cfg << GRUBEOF
# Begin /boot/grub/grub.cfg (tup 0.1)
set default=0
set timeout=5

insmod part_msdos
insmod ext2
set root=(hd0,1)
set gfxpayload=1024x768x32

menuentry "tup 0.1 (Linux ${KERNEL#/boot/vmlinuz-})" {
        linux   $KERNEL root=/dev/vda1 ro console=ttyS0,115200 net.ifnames=0
}
GRUBEOF
grub-script-check /boot/grub/grub.cfg
