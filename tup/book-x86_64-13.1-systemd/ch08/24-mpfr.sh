#!/bin/bash
# 8.24. MPFR-4.2.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/mpfr.html
# TUP_TARBALL=mpfr-4.2.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/24-mpfr.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_ca12b4de2442587f02630b83e30b897ebca31fb380f3927240ae67db0c032541'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr        \
            --disable-static     \
            --enable-thread-safe \
            --docdir=/usr/share/doc/mpfr-4.2.2
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
make html
# TUP_BLOCK_END=002

if tup_tests_enabled "mpfr"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/24-mpfr.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
make install-html
# TUP_BLOCK_END=004
TUP_UNSELECTED_ca12b4de2442587f02630b83e30b897ebca31fb380f3927240ae67db0c032541
