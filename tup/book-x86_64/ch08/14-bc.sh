# 8.14. Bc-7.0.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/bc.html
# TUP_TARBALL=bc-7.0.3.tar.xz

CC='gcc -std=c99' ./configure --prefix=/usr -G -O3 -r

make

if tup_tests_enabled "bc"; then
make test
else tup_receipt_skip_tests "bc"; fi

make install
