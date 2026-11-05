#!/bin/bash
# 8.48. Automake-1.18.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/automake.html
# TUP_TARBALL=automake-1.18.1.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch08/48-automake.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_8d14f57722a270538d0ba301f3ba6ad252e9dacc14a3a5b34e552dbea12603e7'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --docdir=/usr/share/doc/automake-1.18.1
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "automake"; then
# TUP_BLOCK_BEGIN=003
make -j$(($(nproc)>4?$(nproc):4)) check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/48-automake.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_8d14f57722a270538d0ba301f3ba6ad252e9dacc14a3a5b34e552dbea12603e7
