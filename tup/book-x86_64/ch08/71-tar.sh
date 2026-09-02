# 8.71. Tar-1.35
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/tar.html
# TUP_TARBALL=tar-1.35.tar.xz

FORCE_UNSAFE_CONFIGURE=1  \
./configure --prefix=/usr

make

if tup_tests_enabled "tar"; then
make check
else tup_receipt_skip_tests "tar"; fi

make install
make -C doc install-html docdir=/usr/share/doc/tar-1.35
