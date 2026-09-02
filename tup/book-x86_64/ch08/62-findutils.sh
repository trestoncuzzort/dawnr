# 8.62. Findutils-4.10.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/findutils.html
# TUP_TARBALL=findutils-4.10.0.tar.xz

./configure --prefix=/usr --localstatedir=/var/lib/locate

make

if tup_tests_enabled "findutils"; then
chown -R tester .
su tester -c "PATH=$PATH make check"
else tup_receipt_skip_tests "findutils"; fi

make install
