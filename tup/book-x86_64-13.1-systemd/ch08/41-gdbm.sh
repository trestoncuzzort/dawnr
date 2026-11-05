#!/bin/bash
# 8.41. GDBM-1.26
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gdbm.html
# TUP_TARBALL=gdbm-1.26.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/41-gdbm.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_72e4fc2408a38990fb6033e18f94bd85b05343737c71106cc55fea28c561d97e'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --enable-libgdbm-compat
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "gdbm"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/41-gdbm.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_72e4fc2408a38990fb6033e18f94bd85b05343737c71106cc55fea28c561d97e
