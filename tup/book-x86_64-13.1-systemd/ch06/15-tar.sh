#!/bin/bash
# 6.15. Tar-1.35
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/tar.html
# TUP_TARBALL=tar-1.35.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/15-tar.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_cebb43422afb5e296e1ef929e775b12b9c8e0f0289d240d55c2b6eb78e06bea3'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_cebb43422afb5e296e1ef929e775b12b9c8e0f0289d240d55c2b6eb78e06bea3
