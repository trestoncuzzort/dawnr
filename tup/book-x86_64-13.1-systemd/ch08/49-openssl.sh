#!/bin/bash
# 8.49. OpenSSL-4.0.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/openssl.html
# TUP_TARBALL=openssl-4.0.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/49-openssl.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_11224c6ba9df4d69b4dc81b8898c2ca332d9704f9931bce64170a760bb75a174'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./config --prefix=/usr         \
         --openssldir=/etc/ssl \
         --libdir=lib          \
         shared                \
         zlib-dynamic
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "openssl"; then
# TUP_BLOCK_BEGIN=003
make test
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/49-openssl.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make INSTALL_LIBS= MANSUFFIX=ssl install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
mv -v /usr/share/doc/openssl /usr/share/doc/openssl-4.0.1
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
cp -vfr doc/* /usr/share/doc/openssl-4.0.1
# TUP_BLOCK_END=006
TUP_UNSELECTED_11224c6ba9df4d69b4dc81b8898c2ca332d9704f9931bce64170a760bb75a174
