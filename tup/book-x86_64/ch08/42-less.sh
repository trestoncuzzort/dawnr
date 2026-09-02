# 8.42. Less-679
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/less.html
# TUP_TARBALL=less-679.tar.gz

./configure --prefix=/usr --sysconfdir=/etc

make

if tup_tests_enabled "less"; then
make check
else tup_receipt_skip_tests "less"; fi

make install
