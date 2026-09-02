# 8.63. Groff-1.23.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/groff.html
# TUP_TARBALL=groff-1.23.0.tar.gz

PAGE=<paper_size> ./configure --prefix=/usr

make

if tup_tests_enabled "groff"; then
make check
else tup_receipt_skip_tests "groff"; fi

make install
