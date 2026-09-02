# 8.23. MPC-1.3.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/mpc.html
# TUP_TARBALL=mpc-1.3.1.tar.gz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/mpc-1.3.1

make
make html

if tup_tests_enabled "mpc"; then
make check
else tup_receipt_skip_tests "mpc"; fi

make install
make install-html
