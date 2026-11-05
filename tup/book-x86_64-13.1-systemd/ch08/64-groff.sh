#!/bin/bash
# 8.64. Groff-1.24.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/groff.html
# TUP_TARBALL=groff-1.24.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch08/64-groff.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_56b1043276cda16cdaaba149ecf9e63e8b1cdf1e66eb079fac7d66798a9b9055'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
PAGE=<paper_size> ./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make -j1
# TUP_BLOCK_END=002

if tup_tests_enabled "groff"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/64-groff.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_56b1043276cda16cdaaba149ecf9e63e8b1cdf1e66eb079fac7d66798a9b9055
