# 8.11. File-5.46
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/file.html
# TUP_TARBALL=file-5.46.tar.gz

./configure --prefix=/usr

make

if tup_tests_enabled "file"; then
make check
else tup_receipt_skip_tests "file"; fi

make install
