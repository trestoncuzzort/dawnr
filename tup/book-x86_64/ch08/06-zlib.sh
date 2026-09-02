# 8.6. Zlib-1.3.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/zlib.html
# TUP_TARBALL=zlib-1.3.1.tar.gz

./configure --prefix=/usr

make

if tup_tests_enabled "zlib"; then
make check
else tup_receipt_skip_tests "zlib"; fi

make install

rm -fv /usr/lib/libz.a
