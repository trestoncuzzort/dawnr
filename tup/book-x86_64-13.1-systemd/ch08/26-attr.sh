#!/bin/bash
# 8.26. Attr-2.6.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/attr.html
# TUP_TARBALL=attr-2.6.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/26-attr.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_3e0e90fbaadc5fe9a08fcc43eba5cd41e8ba8656ee45ac92a50a4ce328be1441'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr     \
            --disable-static  \
            --sysconfdir=/etc \
            --docdir=/usr/share/doc/attr-2.6.0
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "attr"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/26-attr.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_3e0e90fbaadc5fe9a08fcc43eba5cd41e8ba8656ee45ac92a50a4ce328be1441
