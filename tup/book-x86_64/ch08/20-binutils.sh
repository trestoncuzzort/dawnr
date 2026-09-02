# 8.20. Binutils-2.45
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/binutils.html
# TUP_TARBALL=binutils-2.45.tar.xz

mkdir -v build
cd       build

../configure --prefix=/usr       \
             --sysconfdir=/etc   \
             --enable-ld=default \
             --enable-plugins    \
             --enable-shared     \
             --disable-werror    \
             --enable-64-bit-bfd \
             --enable-new-dtags  \
             --with-system-zlib  \
             --enable-default-hash-style=gnu

make tooldir=/usr

if tup_tests_enabled "binutils"; then
make -k check
else tup_receipt_skip_tests "binutils"; fi

grep '^FAIL:' $(find -name '*.log')   || true   # advisory: see extract_book.py

make tooldir=/usr install

rm -rfv /usr/lib/lib{bfd,ctf,ctf-nobfd,gprofng,opcodes,sframe}.a \
        /usr/share/doc/gprofng/
