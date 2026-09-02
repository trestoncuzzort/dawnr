# 8.60. Diffutils-3.12
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/diffutils.html
# TUP_TARBALL=diffutils-3.12.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "diffutils"; then
make check
else tup_receipt_skip_tests "diffutils"; fi

make install
