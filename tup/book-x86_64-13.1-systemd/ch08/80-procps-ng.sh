#!/bin/bash
# 8.80. Procps-ng-4.0.7
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/procps-ng.html
# TUP_TARBALL=procps-ng-4.0.7.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/80-procps-ng.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_7fc2226cab33f68d41f3ca48a6dea67114bd6acb64d469ed496ddf78ac67ab5c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                           \
            --docdir=/usr/share/doc/procps-ng-4.0.7 \
            --disable-static                        \
            --disable-kill                          \
            --enable-watch8bit                      \
            --with-systemd
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "procps-ng"; then
# TUP_BLOCK_BEGIN=003
chown -R tester .
su tester -c "PATH=$PATH make check"
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/80-procps-ng.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_7fc2226cab33f68d41f3ca48a6dea67114bd6acb64d469ed496ddf78ac67ab5c
