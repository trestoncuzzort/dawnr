#!/bin/bash
# 8.38. Grep-3.12
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grep.html
# TUP_TARBALL=grep-3.12.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/38-grep.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_6794ae7519c74af9fa2807d937e7ff2b0ea1f463b8c6cfaefd55da0fc5eb3cd0'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i "s/echo/#echo/" src/egrep.sh
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "grep"; then
# TUP_BLOCK_BEGIN=004
make check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/38-grep.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005
TUP_UNSELECTED_6794ae7519c74af9fa2807d937e7ff2b0ea1f463b8c6cfaefd55da0fc5eb3cd0
