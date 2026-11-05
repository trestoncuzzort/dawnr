#!/bin/bash
# TUP_TARBALL=linux-6.18.60.tar.xz
# LFS 13.1 chapter 10 kernel procedure, starting from the retained, reviewed
# configuration. That file was resolved with the builder's compiler. Here
# olddefconfig resolves it again with the target toolchain, both checkers must
# accept the result, and the difference is retained for review: it is never
# assumed to be empty.
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/kernel.html
source /tup-layer/common.sh
release=6.18.60-tup
reviewed=/tup-layer/tup/hardware/linux-6.18.60-x86_64.config
export ARCH=x86_64 KCONFIG_WARN_UNKNOWN_SYMBOLS=1 KCONFIG_WERROR=1
make mrproper
cp "$reviewed" .config
make olddefconfig
python3 /tup-layer/tup/boot/kernel.py check --config .config
python3 /tup-layer/tup/hardware/kernel.py check --config .config
status=0
diff -u "$reviewed" .config > /sources/log/linux-config-target-toolchain.diff || status=$?
[ "$status" -le 1 ] || { echo 'cannot compare the resolved kernel configuration' >&2; exit 1; }
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
