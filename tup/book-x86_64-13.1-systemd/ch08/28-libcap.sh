#!/bin/bash
# 8.28. Libcap-2.78
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libcap.html
# TUP_TARBALL=libcap-2.78.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/28-libcap.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_b40b66ab7641fdb7bd259ad73098bc6a5c04fdddcaf2374af13a061ca2c07055'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i '/install -m.*STA/d' libcap/Makefile
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make prefix=/usr lib=lib
# TUP_BLOCK_END=002

if tup_tests_enabled "libcap"; then
# TUP_BLOCK_BEGIN=003
make test
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/28-libcap.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make prefix=/usr lib=lib install
# TUP_BLOCK_END=004
TUP_UNSELECTED_b40b66ab7641fdb7bd259ad73098bc6a5c04fdddcaf2374af13a061ca2c07055
