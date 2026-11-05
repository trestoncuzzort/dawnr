#!/bin/bash
# 8.35. Psmisc-23.7
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/psmisc.html
# TUP_TARBALL=psmisc-23.7.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/35-psmisc.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_c3003b30ff4af9d67a4e05067df85e3190a0aef7155b90460ea73a5b2b97dc6e'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "psmisc"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/35-psmisc.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_c3003b30ff4af9d67a4e05067df85e3190a0aef7155b90460ea73a5b2b97dc6e
