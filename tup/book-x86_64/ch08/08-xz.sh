# 8.8. Xz-5.8.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/xz.html
# TUP_TARBALL=xz-5.8.1.tar.xz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/xz-5.8.1

make

if tup_tests_enabled "xz"; then
make check
else tup_receipt_skip_tests "xz"; fi

make install
