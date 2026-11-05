#!/bin/bash
# TUP_TARBALL=LVM2.2.03.42.tgz
# Device-mapper part only: dracut's live module needs dmsetup, libdevmapper and
# the dm udev rules. Upstream supports exactly this without libaio and without
# any LVM service ("Only libdm part can be build without libaio: make
# [install_]device-mapper", configure.ac of this release). Configure options
# are those of the BLFS LVM2 page.
# https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/lvm2.html
source /tup-layer/common.sh
./configure --prefix=/usr --enable-cmdlib --enable-pkgconfig --enable-udev_sync
make -j"$TUP_JOBS" device-mapper
# The upstream suite creates and removes device-mapper devices. It belongs in a
# disposable booted target, never in this builder; unrun is not a pass.
printf '%s\n' 'LVM2 device-mapper: upstream device regression suite not run here (needs a disposable booted target)'
make install_device-mapper
for path in /usr/sbin/dmsetup /usr/lib/libdevmapper.so /usr/lib/udev/rules.d/10-dm.rules \
            /usr/lib/udev/rules.d/13-dm-disk.rules /usr/lib/udev/rules.d/95-dm-notify.rules; do
  [ -e "$path" ] || { echo "device-mapper installation lacks $path" >&2; exit 1; }
done
# No LVM tool, daemon or unit may have been installed by this partial target.
for path in /usr/sbin/lvm /usr/sbin/lvmpolld /usr/lib/systemd/system/lvm2-monitor.service; do
  [ ! -e "$path" ] || { echo "unexpected LVM component installed: $path" >&2; exit 1; }
done
