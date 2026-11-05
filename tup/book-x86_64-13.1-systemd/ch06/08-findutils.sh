#!/bin/bash
# 6.8. Findutils-4.11.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/findutils.html
# TUP_TARBALL=findutils-4.11.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/08-findutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_93d899a8d51f3e179a06dbd1e361012789ccf30876af611ee5af7128acc230e4'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                   \
            --localstatedir=/var/lib/locate \
            --host=$LFS_TGT                 \
            --build=$(build-aux/config.guess)
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_93d899a8d51f3e179a06dbd1e361012789ccf30876af611ee5af7128acc230e4
