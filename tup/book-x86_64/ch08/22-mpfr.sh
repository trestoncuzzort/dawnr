# 8.22. MPFR-4.2.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/mpfr.html
# TUP_TARBALL=mpfr-4.2.2.tar.xz

./configure --prefix=/usr        \
            --disable-static     \
            --enable-thread-safe \
            --docdir=/usr/share/doc/mpfr-4.2.2

make
make html

if tup_tests_enabled "mpfr"; then
make check
else tup_receipt_skip_tests "mpfr"; fi

make install
make install-html
