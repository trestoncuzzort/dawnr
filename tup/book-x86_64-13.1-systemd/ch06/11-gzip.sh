#!/bin/bash
# 6.11. Gzip-1.14
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/gzip.html
# TUP_TARBALL=gzip-1.14.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/11-gzip.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_414c4f600308ffeeccddb0f005de6d7573408391d1a9cede4c1e56834b6481e5'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --host=$LFS_TGT
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_414c4f600308ffeeccddb0f005de6d7573408391d1a9cede4c1e56834b6481e5
