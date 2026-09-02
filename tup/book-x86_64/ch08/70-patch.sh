# 8.70. Patch-2.8
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/patch.html
# TUP_TARBALL=patch-2.8.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "patch"; then
make check
else tup_receipt_skip_tests "patch"; fi

make install
