# 8.9. Lz4-1.10.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/lz4.html
# TUP_TARBALL=lz4-1.10.0.tar.gz

make BUILD_STATIC=no PREFIX=/usr

if tup_tests_enabled "lz4"; then
make -j1 check
else tup_receipt_skip_tests "lz4"; fi

make BUILD_STATIC=no PREFIX=/usr install
