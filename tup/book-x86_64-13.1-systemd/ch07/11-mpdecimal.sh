#!/bin/bash
# 7.11. mpdecimal-4.0.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/mpdecimal.html
# TUP_TARBALL=mpdecimal-4.0.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/11-mpdecimal.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_72ea3af7b100a277804f380b1bf1c0b92ae69e90f5fabc8433e540e3d0d40cc0'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/mpdecimal-4.0.1
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_72ea3af7b100a277804f380b1bf1c0b92ae69e90f5fabc8433e540e3d0d40cc0
