#!/bin/bash
# 6.16. Xz-5.8.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/xz.html
# TUP_TARBALL=xz-5.8.3.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/16-xz.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_10531b1bed591fe6a843aec7235f1f3e2fce5969f967307349943fc1204b8a9f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                     \
            --host=$LFS_TGT                   \
            --build=$(build-aux/config.guess) \
            --disable-static                  \
            --docdir=/usr/share/doc/xz-5.8.3
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
rm -v $LFS/usr/lib/liblzma.la
# TUP_BLOCK_END=004
TUP_UNSELECTED_10531b1bed591fe6a843aec7235f1f3e2fce5969f967307349943fc1204b8a9f
