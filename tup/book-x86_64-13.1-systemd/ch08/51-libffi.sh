#!/bin/bash
# 8.51. Libffi-3.8.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libffi.html
# TUP_TARBALL=libffi-3.8.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/51-libffi.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_5e29d9883ebd8a10fb03bf44da83ffbfad02cb0e6c0222f8b2e7933b3b3ffdf5'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --with-gcc-arch=native
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "libffi"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/51-libffi.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_5e29d9883ebd8a10fb03bf44da83ffbfad02cb0e6c0222f8b2e7933b3b3ffdf5
