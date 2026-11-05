#!/bin/bash
# 8.11. File-5.48
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/file.html
# TUP_TARBALL=file-5.48.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/11-file.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_d5aea1d2c9265a3d632a21eaa2040790522a3e36143073e524ed729a597ff82b'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "file"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/11-file.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_d5aea1d2c9265a3d632a21eaa2040790522a3e36143073e524ed729a597ff82b
