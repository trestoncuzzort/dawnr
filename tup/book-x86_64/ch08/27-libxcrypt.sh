# 8.27. Libxcrypt-4.4.38
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/libxcrypt.html
# TUP_TARBALL=libxcrypt-4.4.38.tar.xz

./configure --prefix=/usr                \
            --enable-hashes=strong,glibc \
            --enable-obsolete-api=no     \
            --disable-static             \
            --disable-failure-tokens

make

if tup_tests_enabled "libxcrypt"; then
make check
else tup_receipt_skip_tests "libxcrypt"; fi

make install

make distclean
./configure --prefix=/usr                \
            --enable-hashes=strong,glibc \
            --enable-obsolete-api=glibc  \
            --disable-static             \
            --disable-failure-tokens
make
cp -av --remove-destination .libs/libcrypt.so.1* /usr/lib
