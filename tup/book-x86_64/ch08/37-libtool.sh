# 8.37. Libtool-2.5.4
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/libtool.html
# TUP_TARBALL=libtool-2.5.4.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "libtool"; then
make check
else tup_receipt_skip_tests "libtool"; fi

make install

rm -fv /usr/lib/libltdl.a
