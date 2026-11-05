#!/bin/bash
# 8.29. Libxcrypt-4.5.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libxcrypt.html
# TUP_TARBALL=libxcrypt-4.5.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/29-libxcrypt.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_331ee153310bdc01e04ed2abe66b95fc1b5a41c74517b5697820da29878b5605'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i '/strchr/s/const//' lib/crypt-{sm3,gost}-yescrypt.c
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr                \
            --enable-hashes=strong,glibc \
            --enable-obsolete-api=no     \
            --disable-static             \
            --disable-failure-tokens
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "libxcrypt"; then
# TUP_BLOCK_BEGIN=004
make check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/29-libxcrypt.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make distclean
./configure --prefix=/usr                \
            --enable-hashes=strong,glibc \
            --enable-obsolete-api=glibc  \
            --disable-static             \
            --disable-failure-tokens
make
cp -av --remove-destination .libs/libcrypt.so.1* /usr/lib
# TUP_BLOCK_END=006
TUP_UNSELECTED_331ee153310bdc01e04ed2abe66b95fc1b5a41c74517b5697820da29878b5605
