# 8.49. Libelf from Elfutils-0.193
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/libelf.html
# TUP_TARBALL=elfutils-0.193.tar.bz2

./configure --prefix=/usr        \
            --disable-debuginfod \
            --enable-libdebuginfod=dummy

make

if tup_tests_enabled "libelf"; then
make check
else tup_receipt_skip_tests "libelf"; fi

make -C libelf install
install -vm644 config/libelf.pc /usr/lib/pkgconfig
rm /usr/lib/libelf.a
