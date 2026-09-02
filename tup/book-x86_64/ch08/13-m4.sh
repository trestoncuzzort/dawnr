# 8.13. M4-1.4.20
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/m4.html
# TUP_TARBALL=m4-1.4.20.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "m4"; then
make check
else tup_receipt_skip_tests "m4"; fi

make install
