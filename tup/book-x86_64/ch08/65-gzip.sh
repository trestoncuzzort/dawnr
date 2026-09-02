# 8.65. Gzip-1.14
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/gzip.html
# TUP_TARBALL=gzip-1.14.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "gzip"; then
make check
else tup_receipt_skip_tests "gzip"; fi

make install
