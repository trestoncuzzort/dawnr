#!/bin/bash
# 8.14. M4-1.4.21
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/m4.html
# TUP_TARBALL=m4-1.4.21.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/14-m4.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_0da4f8f3bd7639ac7ab3805d4a3a4c5ff14b817d713f7dbfd5933e7c7796b636'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "m4"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/14-m4.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_0da4f8f3bd7639ac7ab3805d4a3a4c5ff14b817d713f7dbfd5933e7c7796b636
