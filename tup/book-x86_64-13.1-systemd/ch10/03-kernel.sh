#!/bin/bash
# 10.3. Linux-7.1.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/kernel.html
# TUP_TARBALL=linux-7.1.8.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch10/03-kernel.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_178a1c727b0d5f376f4df9ad4c1fec73b90d021f93d985c28643f8a398c1ba96'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
make mrproper
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make menuconfig
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make modules_install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
mount /boot
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
cp -iv arch/x86/boot/bzImage /boot/vmlinuz-7.1.8-lfs-13.1-systemd
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cp -iv System.map /boot/System.map-7.1.8
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
cp -iv .config /boot/config-7.1.8
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
cp -r Documentation -T /usr/share/doc/linux-7.1.8
# TUP_BLOCK_END=009
TUP_UNSELECTED_178a1c727b0d5f376f4df9ad4c1fec73b90d021f93d985c28643f8a398c1ba96
