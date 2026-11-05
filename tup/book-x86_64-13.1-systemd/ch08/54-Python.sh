#!/bin/bash
# 8.54. Python-3.14.7
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/Python.html
# TUP_TARBALL=Python-3.14.7.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/54-Python.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_283d9e862fa0b459bf99f1e0a6cfb619a16db9b437cd04e7540dd1bcb5c6e43a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../Python-3.14.7-openssl_4-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr          \
            --enable-shared        \
            --with-system-expat    \
            --enable-optimizations \
            --without-static-libpython
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "Python"; then
# TUP_BLOCK_BEGIN=004
make test TESTOPTS="--timeout 120"
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/54-Python.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
cat > /etc/pip.conf << EOF
[global]
root-user-action = ignore
disable-pip-version-check = true
EOF
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
install -v -dm755 /usr/share/doc/python-3.14.7/html

tar --strip-components=1  \
    --no-same-owner       \
    --no-same-permissions \
    -C /usr/share/doc/python-3.14.7/html \
    -xvf ../python-3.14.7-docs-html.tar.bz2
# TUP_BLOCK_END=007
TUP_UNSELECTED_283d9e862fa0b459bf99f1e0a6cfb619a16db9b437cd04e7540dd1bcb5c6e43a
