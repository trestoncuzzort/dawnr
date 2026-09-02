#!/bin/bash
# OVERRIDE arm64/ch10/kernel: `make menuconfig` is a human at a curses UI, so the
# configuration is made here instead — explicitly, in a file, reviewable.
#
# THE OPTIONS ARE THE BOOK'S, NOT MINE. The page's *commands* say only
# "make menuconfig"; the required configuration lives in the page's PROSE,
# which the command extractor never read. Parsed from
# chapter10/kernel.html on 2026-08-31: 23 symbols, each with the state the
# book shows ([*] enable, [ ] disable). An earlier version of this override
# set ten options of my own choosing and would have failed at the copy step,
# because EFI_ZBOOT — the option that MAKES arch/arm64/boot/vmlinuz.efi
# exist — was not among them. Caught by reading the page instead of the
# commands.
#
# tup adds four of its own on top, marked below: virtio, so the image boots
# under QEMU. They are forced in (=y, not =m) so no initramfs is needed —
# a deliberate simplification that WS-8 retires when tup targets real
# hardware, where storage drivers must be modules and an initramfs must load
# them.
#
# `mount /boot` is dropped: tup keeps /boot on the root filesystem, and the
# ESP holds only GRUB.
set -e

make mrproper
make defconfig

# --- the book's required configuration, verbatim from its prose ----------
for opt in EFI EFI_ZBOOT RELOCATABLE RANDOMIZE_BASE \
           STACKPROTECTOR STACKPROTECTOR_STRONG \
           DEVTMPFS DEVTMPFS_MOUNT SYSFB_SIMPLEFB \
           CGROUPS MEMCG PSI BLK_DEV_NVME \
           DRM DRM_FBDEV_EMULATION DRM_SIMPLEDRM DRM_PANIC \
           FRAMEBUFFER_CONSOLE; do
  ./scripts/config -e "$opt"
done
for opt in EXPERT UEVENT_HELPER WERROR IKHEADERS PSI_DEFAULT_DISABLED; do
  ./scripts/config -d "$opt"
done

# --- tup's own additions: boot under QEMU without an initramfs ------------
for opt in VIRTIO VIRTIO_PCI VIRTIO_BLK VIRTIO_NET VIRTIO_CONSOLE \
           EXT4_FS VFAT_FS NLS_CODEPAGE_437 NLS_ISO8859_1; do
  ./scripts/config -e "$opt"
done

make olddefconfig

# Refuse to build a kernel whose required options did not survive
# olddefconfig — a silently dropped symbol here becomes an unbootable image
# two steps later, and this project does not do silently.
missing=""
for opt in EFI_ZBOOT DEVTMPFS_MOUNT VIRTIO_BLK EXT4_FS; do
  grep -q "^CONFIG_$opt=y" .config || missing="$missing $opt"
done
[ -z "$missing" ] || { echo "!!! kernel config lost:$missing"; exit 1; }
echo "kernel config: required options present"

make
make modules_install

cp -v arch/arm64/boot/vmlinuz.efi /boot/vmlinuz-6.17.3-lfs-arm64-r12.4-42
cp -v System.map /boot/System.map-6.17.3
cp -v .config /boot/config-6.17.3
install -vdm755 /usr/share/doc/linux-6.17.3
cp -r Documentation/* /usr/share/doc/linux-6.17.3

install -v -m755 -d /etc/modprobe.d
cat > /etc/modprobe.d/usb.conf << "USBEOF"
# Begin /etc/modprobe.d/usb.conf

install ohci_hcd /sbin/modprobe ehci_hcd ; /sbin/modprobe -i ohci_hcd ; true
install uhci_hcd /sbin/modprobe ehci_hcd ; /sbin/modprobe -i uhci_hcd ; true

# End /etc/modprobe.d/usb.conf
USBEOF
