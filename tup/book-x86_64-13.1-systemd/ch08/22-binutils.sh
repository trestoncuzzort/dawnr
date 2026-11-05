#!/bin/bash
# 8.22. Binutils-2.47
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/binutils.html
# TUP_TARBALL=binutils-2.47.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/22-binutils.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_1530343df1f9af7d4a4ccadb03c8d0f8fd38af56ddbf71c5cc2f4fbd06e4e632'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -v build
cd       build
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
../configure --prefix=/usr       \
             --sysconfdir=/etc   \
             --enable-ld=default \
             --enable-plugins    \
             --enable-shared     \
             --disable-werror    \
             --enable-64-bit-bfd \
             --enable-new-dtags  \
             --with-system-zlib  \
             --with-lib-path=/usr/lib \
             --enable-default-hash-style=gnu
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make tooldir=/usr
# TUP_BLOCK_END=003

if tup_tests_enabled "binutils"; then
# TUP_BLOCK_BEGIN=004
make -k check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/22-binutils.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
grep '^FAIL:' $(find -name '*.log')
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make tooldir=/usr install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
rm -rfv /usr/lib/lib{bfd,ctf,ctf-nobfd,gprofng,opcodes,sframe}.a \
        /usr/share/doc/gprofng/
# TUP_BLOCK_END=007
TUP_UNSELECTED_1530343df1f9af7d4a4ccadb03c8d0f8fd38af56ddbf71c5cc2f4fbd06e4e632
