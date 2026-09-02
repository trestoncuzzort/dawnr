# 8.10. Zstd-1.5.7
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/zstd.html
# TUP_TARBALL=zstd-1.5.7.tar.gz

make prefix=/usr

if tup_tests_enabled "zstd"; then
make check
else tup_receipt_skip_tests "zstd"; fi

make prefix=/usr install

rm -v /usr/lib/libzstd.a
