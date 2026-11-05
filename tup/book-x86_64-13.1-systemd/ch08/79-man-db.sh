#!/bin/bash
# 8.79. Man-DB-2.13.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/man-db.html
# TUP_TARBALL=man-db-2.13.1.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/79-man-db.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_0965a6f3e9b6f1d40f4ade1d09ce409c95e1721d7efb0a6b78bf0c09fcb61f9c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                         \
            --docdir=/usr/share/doc/man-db-2.13.1 \
            --sysconfdir=/etc                     \
            --disable-setuid                      \
            --enable-cache-owner=bin              \
            --with-browser=/usr/bin/lynx          \
            --with-vgrind=/usr/bin/vgrind         \
            --with-grap=/usr/bin/grap
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "man-db"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/79-man-db.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_0965a6f3e9b6f1d40f4ade1d09ce409c95e1721d7efb0a6b78bf0c09fcb61f9c
