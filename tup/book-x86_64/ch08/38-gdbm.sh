# 8.38. GDBM-1.26
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/gdbm.html
# TUP_TARBALL=gdbm-1.26.tar.gz

./configure --prefix=/usr    \
            --disable-static \
            --enable-libgdbm-compat

make

if tup_tests_enabled "gdbm"; then
make check
else tup_receipt_skip_tests "gdbm"; fi

make install
