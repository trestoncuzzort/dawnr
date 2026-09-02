# 8.46. Autoconf-2.72
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/autoconf.html
# TUP_TARBALL=autoconf-2.72.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "autoconf"; then
make check
else tup_receipt_skip_tests "autoconf"; fi

make install
