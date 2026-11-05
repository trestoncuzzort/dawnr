#!/bin/bash
# 8.60. Kmod-34.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/kmod.html
# TUP_TARBALL=kmod-34.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/60-kmod.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_5693385a93b1e7ba9791973660e369ae8504d1384633f759e4a72072c4f497f3'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -p build
cd       build

meson setup --prefix=/usr ..    \
            --buildtype=release \
            -D manpages=false
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
ninja
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
ninja install
# TUP_BLOCK_END=003
TUP_UNSELECTED_5693385a93b1e7ba9791973660e369ae8504d1384633f759e4a72072c4f497f3
