#!/bin/bash
# 8.40. Libtool-2.6.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libtool.html
# TUP_TARBALL=libtool-2.6.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/40-libtool.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_ea4da37ce7334e82a8d759385c027a92737825b037f41d1ed7bc41f0debdf91a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "libtool"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/40-libtool.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
rm -fv /usr/lib/libltdl.a
# TUP_BLOCK_END=005
TUP_UNSELECTED_ea4da37ce7334e82a8d759385c027a92737825b037f41d1ed7bc41f0debdf91a
