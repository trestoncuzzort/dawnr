# 8.35. Grep-3.12
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/grep.html
# TUP_TARBALL=grep-3.12.tar.xz

sed -i "s/echo/#echo/" src/egrep.sh

./configure --prefix=/usr

make

if tup_tests_enabled "grep"; then
make check
else tup_receipt_skip_tests "grep"; fi

make install
