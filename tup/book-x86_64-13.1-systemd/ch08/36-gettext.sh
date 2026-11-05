#!/bin/bash
# 8.36. Gettext-1.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gettext.html
# TUP_TARBALL=gettext-1.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/36-gettext.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_5a8f8e8c99376a203af9da325fb92afec4f4d4391ff1d8119901c1ce64539b28'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/gettext-1.0
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "gettext"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/36-gettext.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
chmod -v 0755 /usr/lib/preloadable_libintl.so
# TUP_BLOCK_END=004
TUP_UNSELECTED_5a8f8e8c99376a203af9da325fb92afec4f4d4391ff1d8119901c1ce64539b28
