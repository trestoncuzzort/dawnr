#!/bin/bash
# 5.4. Linux-7.1.8 API Headers
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter05/linux-headers.html
# TUP_TARBALL=linux-7.1.8.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch05/04-linux-headers.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_763a1d838a877912b8a3dd4f259daeec41499d118eafd3ec8e299491f59c6402'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
make mrproper
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make headers
find usr/include -type f ! -name '*.h' -delete
cp -rv usr/include $LFS/usr
# TUP_BLOCK_END=002
TUP_UNSELECTED_763a1d838a877912b8a3dd4f259daeec41499d118eafd3ec8e299491f59c6402
