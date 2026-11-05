#!/bin/bash
# 8.43. Expat-2.8.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/expat.html
# TUP_TARBALL=expat-2.8.3.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/43-expat.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_bf2d81a30b9f8d5446764014a312d30fc4b70c52f549bb151c9a10df851c9ab9'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/expat-2.8.3
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "expat"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/43-expat.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
install -v -m644 doc/*.{html,css} /usr/share/doc/expat-2.8.3
# TUP_BLOCK_END=005
TUP_UNSELECTED_bf2d81a30b9f8d5446764014a312d30fc4b70c52f549bb151c9a10df851c9ab9
