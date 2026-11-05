#!/bin/bash
# 8.78. D-Bus-1.16.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/dbus.html
# TUP_TARBALL=dbus-1.16.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/78-dbus.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_2eb47a9d692f68af86931ba51f1eedbc9f0190f0afbac0d08d93a8631c4f89d4'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir build
cd    build

meson setup --prefix=/usr --buildtype=release --wrap-mode=nofallback ..
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
ninja
# TUP_BLOCK_END=002

if tup_tests_enabled "dbus"; then
# TUP_BLOCK_BEGIN=003
ninja test
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/78-dbus.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
ninja install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
ln -sfv /etc/machine-id /var/lib/dbus
# TUP_BLOCK_END=005
TUP_UNSELECTED_2eb47a9d692f68af86931ba51f1eedbc9f0190f0afbac0d08d93a8631c4f89d4
