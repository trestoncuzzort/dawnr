#!/bin/bash
# 6.10. Grep-3.12
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/grep.html
# TUP_TARBALL=grep-3.12.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/10-grep.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_756725c91feeb8c0a0ea81bab9cbcb73124d7974225808e992168c7d6a85a7ac'
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
TUP_UNSELECTED_756725c91feeb8c0a0ea81bab9cbcb73124d7974225808e992168c7d6a85a7ac
