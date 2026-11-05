#!/bin/bash
# 8.10. Zstd-1.5.7
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/zstd.html
# TUP_TARBALL=zstd-1.5.7.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/10-zstd.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a8d247667ce4b038c6da0fed2e33404c4b9e7953d416df836b8ac7cd10cec2e5'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
make prefix=/usr
# TUP_BLOCK_END=001

if tup_tests_enabled "zstd"; then
# TUP_BLOCK_BEGIN=002
make check
# TUP_BLOCK_END=002
else tup_receipt_skip_tests "ch08/10-zstd.sh:block-002"; fi

# TUP_BLOCK_BEGIN=003
make prefix=/usr install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
rm -v /usr/lib/libzstd.a
# TUP_BLOCK_END=004
TUP_UNSELECTED_a8d247667ce4b038c6da0fed2e33404c4b9e7953d416df836b8ac7cd10cec2e5
