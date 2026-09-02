# 8.25. Acl-2.3.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/acl.html
# TUP_TARBALL=acl-2.3.2.tar.xz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/acl-2.3.2

make

if tup_tests_enabled "acl"; then
make check
else tup_receipt_skip_tests "acl"; fi

make install
