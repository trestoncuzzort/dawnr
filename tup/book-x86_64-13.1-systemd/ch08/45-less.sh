#!/bin/bash
# 8.45. Less-704
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/less.html
# TUP_TARBALL=less-704.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/45-less.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_d66208f66d0415e6a84b01cac10488601a27beca184bf21ca2fa03ef9b79fad6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --sysconfdir=/etc
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "less"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/45-less.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_d66208f66d0415e6a84b01cac10488601a27beca184bf21ca2fa03ef9b79fad6
