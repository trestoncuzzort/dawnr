#!/bin/bash
# 7.10. Zlib-1.3.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/zlib.html
# TUP_TARBALL=zlib-1.3.2.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/10-zlib.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_43654791a78bf7ace3ebb8d10481e8bec48a94149ea73835385305209f4696d6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
rm -fv /usr/lib/libz.a
# TUP_BLOCK_END=004
TUP_UNSELECTED_43654791a78bf7ace3ebb8d10481e8bec48a94149ea73835385305209f4696d6
