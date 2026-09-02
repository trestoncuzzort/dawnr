# 8.34. Bison-3.8.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/bison.html
# TUP_TARBALL=bison-3.8.2.tar.xz

./configure --prefix=/usr --docdir=/usr/share/doc/bison-3.8.2

make

if tup_tests_enabled "bison"; then
make check
else tup_receipt_skip_tests "bison"; fi

make install
