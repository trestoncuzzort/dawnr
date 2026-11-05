#!/bin/bash
# 8.67. IPRoute2-7.1.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/iproute2.html
# TUP_TARBALL=iproute2-7.1.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/67-iproute2.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_37f97ebd6c2d2261a620fcdda3ac457ac3c55f5ecdd8f0017c2f6245d85e75d9'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i /ARPD/d Makefile
rm -fv man/man8/arpd.8
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make NETNS_RUN_DIR=/run/netns
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make SBINDIR=/usr/sbin install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
install -vDm644 COPYING README* -t /usr/share/doc/iproute2-7.1.0
# TUP_BLOCK_END=004
TUP_UNSELECTED_37f97ebd6c2d2261a620fcdda3ac457ac3c55f5ecdd8f0017c2f6245d85e75d9
