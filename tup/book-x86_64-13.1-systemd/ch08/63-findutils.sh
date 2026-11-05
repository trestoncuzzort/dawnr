#!/bin/bash
# 8.63. Findutils-4.11.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/findutils.html
# TUP_TARBALL=findutils-4.11.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/63-findutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a224d4bc6996d2a7fc57c8c978d6bc47544c1f86a3932bea9aa0ae8a5cb27c06'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --localstatedir=/var/lib/locate
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "findutils"; then
# TUP_BLOCK_BEGIN=003
chown -R tester .
su tester -c "PATH=$PATH make check -k"
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/63-findutils.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_a224d4bc6996d2a7fc57c8c978d6bc47544c1f86a3932bea9aa0ae8a5cb27c06
