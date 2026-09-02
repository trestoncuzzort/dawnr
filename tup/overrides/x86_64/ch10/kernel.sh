#!/bin/bash
# OVERRIDE x86_64/ch10/kernel: `make menuconfig` is a human at a curses UI,
# so the configuration is made here instead: explicitly, in a file,
# reviewable. Every other line of the page runs as the book wrote it, with
# two named substitutions (below).
#
# THE OPTIONS ARE THE BOOK'S, NOT MINE. The page's commands say only "make
# menuconfig"; the required configuration lives in the page's PROSE, which
# the command extractor never reads. Parsed from the x86 12.4 book's
# chapter10/kernel.html on 2026-09-02: 21 symbols with the state the book
# shows ([*] enable, [ ] disable, (kmsg) string), plus the "64-bit system"
# block the page adds for x86 (X86_X2APIC, PCI_MSI, IRQ_REMAP, in the order
# the page says their dependencies require) and its NVMe note. The arm64
# lesson applies unchanged: an earlier arm64 override chose its own options
# and would have failed at the copy step because EFI_ZBOOT was not among
# them. Caught by reading the page instead of the commands.
#
# tup adds virtio and the serial console on top, marked below, so the image
# boots under QEMU and speaks on ttyS0. They are forced in (=y, not =m) so no
# initramfs is needed, the same deliberate simplification the arm64 leg
# made; WS-8 retires it if tup ever targets real hardware.
#
# Substitutions on the page's own bytes, both line-preserving:
#   make menuconfig  -> tup_configure_kernel   (this file's configuration)
#   mount /boot      -> no-op: tup keeps /boot on the root filesystem
#   cp -iv           -> cp -v: -i would read its answer from /dev/null
set -e

tup_configure_kernel() {
  make defconfig

  # --- the book's required configuration, verbatim from its prose --------
  for opt in PSI CGROUPS MEMCG RELOCATABLE RANDOMIZE_BASE \
             STACKPROTECTOR STACKPROTECTOR_STRONG \
             DEVTMPFS DEVTMPFS_MOUNT SYSFB_SIMPLEFB \
             DRM DRM_PANIC DRM_FBDEV_EMULATION DRM_SIMPLEDRM \
             FRAMEBUFFER_CONSOLE; do
    ./scripts/config -e "$opt"
  done
  ./scripts/config --set-str DRM_PANIC_SCREEN kmsg
  for opt in WERROR PSI_DEFAULT_DISABLED IKHEADERS EXPERT UEVENT_HELPER; do
    ./scripts/config -d "$opt"
  done
  # "Enable some additional features if you are building a 64-bit system",
  # in the order the page prescribes: PCI_MSI, then IRQ_REMAP, then X86_X2APIC.
  for opt in PCI PCI_MSI IOMMU_SUPPORT IRQ_REMAP X86_X2APIC; do
    ./scripts/config -e "$opt"
  done
  ./scripts/config -e BLK_DEV_NVME

  # --- tup's own additions: boot under QEMU, talk on the serial port -------
  for opt in VIRTIO VIRTIO_PCI VIRTIO_BLK VIRTIO_NET VIRTIO_CONSOLE \
             EXT4_FS VFAT_FS NLS_CODEPAGE_437 NLS_ISO8859_1 \
             SERIAL_8250 SERIAL_8250_CONSOLE; do
    ./scripts/config -e "$opt"
  done

  make olddefconfig

  # Refuse to build a kernel whose required options did not survive
  # olddefconfig: a silently dropped symbol here becomes an unbootable image
  # two steps later, and this project does not do silently.
  local missing=""
  for opt in DEVTMPFS_MOUNT VIRTIO_BLK VIRTIO_PCI EXT4_FS \
             SERIAL_8250_CONSOLE X86_X2APIC PCI_MSI IRQ_REMAP; do
    grep -q "^CONFIG_$opt=y" .config || missing="$missing $opt"
  done
  [ -z "$missing" ] || { echo "!!! kernel config lost:$missing"; exit 1; }
  echo "kernel config: required options present"
}
export -f tup_configure_kernel

PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the kernel page"; exit 1; }
sed -e 's@^make menuconfig$@tup_configure_kernel@' \
    -e 's@^mount /boot$@: # /boot stays on the root filesystem (tup)@' \
    -e 's@^cp -iv @cp -v @' \
    "$PAGE" > /tmp/kernel-page.sh
grep -q '^tup_configure_kernel$' /tmp/kernel-page.sh || { echo "override: menuconfig substitution missed"; exit 1; }
grep -q '^cp -v arch/x86/boot/bzImage /boot/vmlinuz-' /tmp/kernel-page.sh || { echo "override: no bzImage copy on this page"; exit 1; }
[ "$(grep -c . "$PAGE")" = "$(grep -c . /tmp/kernel-page.sh)" ] || { echo "override: line count changed"; exit 1; }
bash -e /tmp/kernel-page.sh < /dev/null
