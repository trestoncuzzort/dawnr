#!/bin/bash
# 8.71. Patch-2.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/patch.html
# TUP_TARBALL=patch-2.8.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/71-patch.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_08e817d3f39fa2308ad86a96b0fd78bc11b8012f2d06ea41075c12edda2d2708'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "patch"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/71-patch.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_08e817d3f39fa2308ad86a96b0fd78bc11b8012f2d06ea41075c12edda2d2708
