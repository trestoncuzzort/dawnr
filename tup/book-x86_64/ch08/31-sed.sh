# 8.31. Sed-4.9
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/sed.html
# TUP_TARBALL=sed-4.9.tar.xz

./configure --prefix=/usr

make
make html

if tup_tests_enabled "sed"; then
chown -R tester .
su tester -c "PATH=$PATH make check"
else tup_receipt_skip_tests "sed"; fi

make install
install -d -m755           /usr/share/doc/sed-4.9
install -m644 doc/sed.html /usr/share/doc/sed-4.9
