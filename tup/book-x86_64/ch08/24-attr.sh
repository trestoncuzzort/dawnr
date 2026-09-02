# 8.24. Attr-2.5.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/attr.html
# TUP_TARBALL=attr-2.5.2.tar.gz

./configure --prefix=/usr     \
            --disable-static  \
            --sysconfdir=/etc \
            --docdir=/usr/share/doc/attr-2.5.2

make

if tup_tests_enabled "attr"; then
make check
else tup_receipt_skip_tests "attr"; fi

make install
