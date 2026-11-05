#!/bin/bash
# 8.15. Bc-7.0.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/bc.html
# TUP_TARBALL=bc-7.0.3.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/15-bc.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_e4198bdddd40fdc529cb62d073a10404d5abb432331a2394afef28ee9b59d3b7'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
CC='gcc -std=c99' ./configure --prefix=/usr -G -O3 -r
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "bc"; then
# TUP_BLOCK_BEGIN=003
make test
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/15-bc.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_e4198bdddd40fdc529cb62d073a10404d5abb432331a2394afef28ee9b59d3b7
