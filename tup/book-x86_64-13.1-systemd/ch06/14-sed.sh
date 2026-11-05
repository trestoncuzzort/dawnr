#!/bin/bash
# 6.14. Sed-4.10
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/sed.html
# TUP_TARBALL=sed-4.10.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/14-sed.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_79949717f18be04e67420335bc4bf75bcb9cdb95f9ad4f4e1e6ce2a583bd21a6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(./build-aux/config.guess)
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_79949717f18be04e67420335bc4bf75bcb9cdb95f9ad4f4e1e6ce2a583bd21a6
