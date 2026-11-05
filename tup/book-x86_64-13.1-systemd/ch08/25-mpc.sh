#!/bin/bash
# 8.25. MPC-1.4.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/mpc.html
# TUP_TARBALL=mpc-1.4.1.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/25-mpc.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_4e08dee8be7b71c89f21cc763f54f30dae9f1dfff57238a75c85e57d6436b838'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/mpc-1.4.1
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
make html
# TUP_BLOCK_END=002

if tup_tests_enabled "mpc"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/25-mpc.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
make install-html
# TUP_BLOCK_END=004
TUP_UNSELECTED_4e08dee8be7b71c89f21cc763f54f30dae9f1dfff57238a75c85e57d6436b838
