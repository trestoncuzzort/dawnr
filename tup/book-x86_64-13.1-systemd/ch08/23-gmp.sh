#!/bin/bash
# 8.23. GMP-6.3.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gmp.html
# TUP_TARBALL=gmp-6.3.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/23-gmp.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_810e373ef2f977ee7a9d3ac053fa0c3ae86097ed27f29ee18f1b1c7e3824ee05'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
ABI=32 ./configure ...
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed -i '/long long t1;/,+1s/()/(...)/' configure
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
./configure --prefix=/usr    \
            --enable-cxx     \
            --disable-static \
            --docdir=/usr/share/doc/gmp-6.3.0
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
make html
# TUP_BLOCK_END=004

if tup_tests_enabled "gmp"; then
# TUP_BLOCK_BEGIN=005
make check
# TUP_BLOCK_END=005
else tup_receipt_skip_tests "ch08/23-gmp.sh:block-005"; fi

# TUP_BLOCK_BEGIN=006
cat $(find -name '*.log') | grep -c ^PASS
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
make install
make install-html
# TUP_BLOCK_END=007
TUP_UNSELECTED_810e373ef2f977ee7a9d3ac053fa0c3ae86097ed27f29ee18f1b1c7e3824ee05
