#!/bin/bash
# 8.47. Autoconf-2.73
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/autoconf.html
# TUP_TARBALL=autoconf-2.73.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/47-autoconf.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_180c852cee134daea06c40b856a69d0241a5ba9097596b4513452c955cb35607'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "autoconf"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/47-autoconf.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_180c852cee134daea06c40b856a69d0241a5ba9097596b4513452c955cb35607
