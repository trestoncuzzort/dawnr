#!/bin/bash
# 8.70. Make-4.4.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/make.html
# TUP_TARBALL=make-4.4.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/70-make.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_76affde6f2f8617c054cdcd3358fe70aeccb7eace876d4fccab8cee3d3d184a9'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "make"; then
# TUP_BLOCK_BEGIN=003
chown -R tester .
su tester -c "PATH=$PATH make check"
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/70-make.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_76affde6f2f8617c054cdcd3358fe70aeccb7eace876d4fccab8cee3d3d184a9
