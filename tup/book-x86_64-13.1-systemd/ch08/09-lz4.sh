#!/bin/bash
# 8.9. Lz4-1.10.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/lz4.html
# TUP_TARBALL=lz4-1.10.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/09-lz4.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_ed7c1254790f3c41176c42ecefae5845a72e1b07453d5c9331fbf72b3ab31b30'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
make BUILD_STATIC=no PREFIX=/usr
# TUP_BLOCK_END=001

if tup_tests_enabled "lz4"; then
# TUP_BLOCK_BEGIN=002
make -j1 check
# TUP_BLOCK_END=002
else tup_receipt_skip_tests "ch08/09-lz4.sh:block-002"; fi

# TUP_BLOCK_BEGIN=003
make BUILD_STATIC=no PREFIX=/usr install
# TUP_BLOCK_END=003
TUP_UNSELECTED_ed7c1254790f3c41176c42ecefae5845a72e1b07453d5c9331fbf72b3ab31b30
