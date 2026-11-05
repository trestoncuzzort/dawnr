#!/bin/bash
# 8.6. Zlib-1.3.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/zlib.html
# TUP_TARBALL=zlib-1.3.2.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/06-zlib.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_845e12863788909c5a32e47bf79ee4dd93d853bfa20dbf90299e85cd9672e26d'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "zlib"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/06-zlib.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
rm -fv /usr/lib/libz.a
# TUP_BLOCK_END=005
TUP_UNSELECTED_845e12863788909c5a32e47bf79ee4dd93d853bfa20dbf90299e85cd9672e26d
