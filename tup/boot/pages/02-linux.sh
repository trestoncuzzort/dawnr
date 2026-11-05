#!/bin/bash
# TUP_TARBALL=linux-6.18.60.tar.xz
# LFS 13.1 chapter 10 kernel procedure with the reviewed boot and hardware
# fragments merged into x86_64_defconfig by the kernel's own merge_config.sh.
# The retained Kconfig qualification used the builder's compiler; resolution is
# repeated here with the target toolchain and rechecked, never assumed equal.
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/kernel.html
source /tup-layer/common.sh
release=6.18.60-tup
export ARCH=x86_64 KCONFIG_WARN_UNKNOWN_SYMBOLS=1 KCONFIG_WERROR=1
make mrproper
python3 /tup-layer/tup/boot/kernel.py fragment > tup-boot.config
python3 /tup-layer/tup/hardware/kernel.py fragment > tup-hardware.config
make x86_64_defconfig
bash scripts/kconfig/merge_config.sh -m .config tup-boot.config tup-hardware.config
make olddefconfig
python3 /tup-layer/tup/boot/kernel.py check --config .config
python3 /tup-layer/tup/hardware/kernel.py check --config .config
[ "$(make -s kernelrelease)" = "$release" ] || { echo 'kernel release differs from the packaging contract' >&2; exit 1; }
make -j"$TUP_JOBS" bzImage modules
[ ! -e "/usr/lib/modules/$release" ] || { echo 'module tree already exists' >&2; exit 1; }
make modules_install
install -d -m 0755 /boot
install -m 0644 arch/x86/boot/bzImage "/boot/vmlinuz-$release"
install -m 0644 .config "/boot/config-$release"
install -m 0644 System.map "/boot/System.map-$release"
# The driver removes this source tree; do not leave links into it. A prepared
# build tree for external modules is a later, separate layer.
for link in build source; do
  if [ -L "/usr/lib/modules/$release/$link" ]; then rm -- "/usr/lib/modules/$release/$link"; fi
done
for name in modules.dep modules.alias modules.builtin modules.builtin.modinfo modules.order; do
  [ -s "/usr/lib/modules/$release/$name" ] || { echo "module metadata is missing: $name" >&2; exit 1; }
done
