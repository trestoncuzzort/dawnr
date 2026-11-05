#!/bin/bash
# 6.13. Patch-2.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/patch.html
# TUP_TARBALL=patch-2.8.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/13-patch.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_f3ad96a311d86f355ec3e4bc281239e68fbedf5f0d70fc4f38a3a23447b1fa68'
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
TUP_UNSELECTED_f3ad96a311d86f355ec3e4bc281239e68fbedf5f0d70fc4f38a3a23447b1fa68
