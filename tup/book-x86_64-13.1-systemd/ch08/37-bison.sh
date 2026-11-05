#!/bin/bash
# 8.37. Bison-3.8.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/bison.html
# TUP_TARBALL=bison-3.8.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/37-bison.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_77caf63206159a3b17658b2e3eb15408d90565a7cba98a9a1097496e8f916fd3'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --docdir=/usr/share/doc/bison-3.8.2
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "bison"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/37-bison.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_77caf63206159a3b17658b2e3eb15408d90565a7cba98a9a1097496e8f916fd3
