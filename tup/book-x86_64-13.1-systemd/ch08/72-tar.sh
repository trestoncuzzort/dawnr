#!/bin/bash
# 8.72. Tar-1.35
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/tar.html
# TUP_TARBALL=tar-1.35.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/72-tar.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_b36ada81e6428a88edc3ac55921d56a7cc1bf44327d3d7aad03c6d535444760d'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../tar-1.35-acl_fix-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
FORCE_UNSAFE_CONFIGURE=1  \
./configure --prefix=/usr
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "tar"; then
# TUP_BLOCK_BEGIN=004
make check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/72-tar.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
make -C doc install-html docdir=/usr/share/doc/tar-1.35
# TUP_BLOCK_END=005
TUP_UNSELECTED_b36ada81e6428a88edc3ac55921d56a7cc1bf44327d3d7aad03c6d535444760d
