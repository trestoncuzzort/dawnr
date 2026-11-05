#!/bin/bash
# 8.62. Diffutils-3.12
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/diffutils.html
# TUP_TARBALL=diffutils-3.12.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/62-diffutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_01a17580cb3a81ed0b1b9cd12881eac1dd2da75a90b4ba87f8895193e6c5e347'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "diffutils"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/62-diffutils.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_01a17580cb3a81ed0b1b9cd12881eac1dd2da75a90b4ba87f8895193e6c5e347
