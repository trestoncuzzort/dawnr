#!/bin/bash
# 8.66. Gzip-1.14
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gzip.html
# TUP_TARBALL=gzip-1.14.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/66-gzip.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_285abbf3dd62f15ef315cf2d07fd21a21e1928cdf7d0d190054413b6e5d00d0b'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "gzip"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/66-gzip.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_285abbf3dd62f15ef315cf2d07fd21a21e1928cdf7d0d190054413b6e5d00d0b
