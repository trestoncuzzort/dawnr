#!/bin/bash
# 8.16. Flex-2.6.4
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/flex.html
# TUP_TARBALL=flex-2.6.4.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/16-flex.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a1f972a66dd0b7c4c8741b462e4c53d3c65e6b54b0b26f6d40e25783fa6437ab'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/flex-2.6.4
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "flex"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/16-flex.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
ln -sv flex   /usr/bin/lex
ln -sv flex.1 /usr/share/man/man1/lex.1
# TUP_BLOCK_END=005
TUP_UNSELECTED_a1f972a66dd0b7c4c8741b462e4c53d3c65e6b54b0b26f6d40e25783fa6437ab
