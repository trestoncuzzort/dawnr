# 8.26. Libcap-2.76
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/libcap.html
# TUP_TARBALL=libcap-2.76.tar.xz

sed -i '/install -m.*STA/d' libcap/Makefile

make prefix=/usr lib=lib

if tup_tests_enabled "libcap"; then
make test
else tup_receipt_skip_tests "libcap"; fi

make prefix=/usr lib=lib install
