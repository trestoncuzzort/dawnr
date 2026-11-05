#!/bin/bash
# 8.53. mpdecimal-4.0.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/mpdecimal.html
# TUP_TARBALL=mpdecimal-4.0.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/53-mpdecimal.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_c4ae42f159a7226f2e93943a9155f9b11427f1959a0687631bf1aced126a8220'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/mpdecimal-4.0.1
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "mpdecimal"; then
# TUP_BLOCK_BEGIN=003
make check_local
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/53-mpdecimal.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_c4ae42f159a7226f2e93943a9155f9b11427f1959a0687631bf1aced126a8220
