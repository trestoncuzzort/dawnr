#!/bin/bash
# 8.27. Acl-2.4.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/acl.html
# TUP_TARBALL=acl-2.4.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/27-acl.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_7a5a5d2bc4054d4a89e4e8fb2a233b904e1b0ddbb7d7c24cdd50e42bb7bca719'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/acl-2.4.0
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "acl"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/27-acl.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_7a5a5d2bc4054d4a89e4e8fb2a233b904e1b0ddbb7d7c24cdd50e42bb7bca719
