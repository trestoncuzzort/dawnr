# 8.33. Gettext-0.26
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/gettext.html
# TUP_TARBALL=gettext-0.26.tar.xz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/gettext-0.26

make

if tup_tests_enabled "gettext"; then
make check
else tup_receipt_skip_tests "gettext"; fi

make install
chmod -v 0755 /usr/lib/preloadable_libintl.so
