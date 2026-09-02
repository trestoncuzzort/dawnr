# 8.32. Psmisc-23.7
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/psmisc.html
# TUP_TARBALL=psmisc-23.7.tar.xz

./configure --prefix=/usr

make

if tup_tests_enabled "psmisc"; then
make check
else tup_receipt_skip_tests "psmisc"; fi

make install
