#!/bin/bash
# 8.50. Libelf from Elfutils-0.195
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libelf.html
# TUP_TARBALL=elfutils-0.195.tar.bz2
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/50-libelf.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_b6c811bceb74fbec86b13614034095e42c986cf33e2077b7a8ab89aa0eb114dd'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr        \
            --disable-debuginfod \
            --enable-libdebuginfod=dummy
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make -C lib
make -C libelf
# TUP_BLOCK_END=002

if tup_tests_enabled "libelf"; then
# TUP_BLOCK_BEGIN=003
make -k check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/50-libelf.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make -C libelf install
install -vm644 config/libelf.pc /usr/lib/pkgconfig
rm /usr/lib/libelf.a
# TUP_BLOCK_END=004
TUP_UNSELECTED_b6c811bceb74fbec86b13614034095e42c986cf33e2077b7a8ab89aa0eb114dd
