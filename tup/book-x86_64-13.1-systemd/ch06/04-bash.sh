#!/bin/bash
# 6.4. Bash-5.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/bash.html
# TUP_TARBALL=bash-5.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/04-bash.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_5268315c27833bcf53f0af606d47f437cb4bbf86cadfee4599dc014e59a4628f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                      \
            --build=$(sh support/config.guess) \
            --host=$LFS_TGT                    \
            --without-bash-malloc              \
            --docdir=/usr/share/doc/bash-5.3
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
ln -sv bash $LFS/bin/sh
# TUP_BLOCK_END=004
TUP_UNSELECTED_5268315c27833bcf53f0af606d47f437cb4bbf86cadfee4599dc014e59a4628f
