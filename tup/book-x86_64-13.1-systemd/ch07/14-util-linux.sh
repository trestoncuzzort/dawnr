#!/bin/bash
# 7.14. Util-linux-2.42.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/util-linux.html
# TUP_TARBALL=util-linux-2.42.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/14-util-linux.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_d92b306a1a2921333b16f44fdfac499a76217c04ccef123c7e941513fc04eab7'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -pv /var/lib/hwclock
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --libdir=/usr/lib     \
            --runstatedir=/run    \
            --disable-chfn-chsh   \
            --disable-login       \
            --disable-nologin     \
            --disable-su          \
            --disable-setpriv     \
            --disable-runuser     \
            --disable-pylibmount  \
            --disable-static      \
            --disable-liblastlog2 \
            --without-python      \
            ADJTIME_PATH=/var/lib/hwclock/adjtime \
            --docdir=/usr/share/doc/util-linux-2.42.2
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_d92b306a1a2921333b16f44fdfac499a76217c04ccef123c7e941513fc04eab7
