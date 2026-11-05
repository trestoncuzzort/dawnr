#!/bin/bash
# TUP_TARBALL=linux-firmware-20261019.tar.xz
# BLFS explicit selected-file firmware installation: only the reviewed Realtek
# RTL8125 alternatives, the AMD family 19h microcode container and their two
# licence notices. The release's copy-firmware.sh would install everything.
# https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/firmware.html
source /tup-layer/common.sh
sha256sum --check --strict /tup-layer/tup/hardware/firmware-files.sha256
for name in rtl8125a-3.fw rtl8125b-2.fw rtl8125d-1.fw rtl8125d-2.fw rtl8125bp-2.fw; do
  install -D -m 0644 "rtl_nic/$name" "/usr/lib/firmware/rtl_nic/$name"
done
install -D -m 0644 amd-ucode/microcode_amd_fam19h.bin \
  /usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin
for name in LICENSE.r8169 LICENSE.amd-ucode; do
  install -D -m 0644 "LICENSES/$name" "/usr/share/licenses/linux-firmware/$name"
done
[ "$(find /usr/lib/firmware -type f | wc -l)" = 6 ] || { echo 'unexpected firmware file set' >&2; exit 1; }
