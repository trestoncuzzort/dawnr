# 8.77. Man-DB-2.13.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/man-db.html
# TUP_TARBALL=man-db-2.13.1.tar.xz

./configure --prefix=/usr                         \
            --docdir=/usr/share/doc/man-db-2.13.1 \
            --sysconfdir=/etc                     \
            --disable-setuid                      \
            --enable-cache-owner=bin              \
            --with-browser=/usr/bin/lynx          \
            --with-vgrind=/usr/bin/vgrind         \
            --with-grap=/usr/bin/grap             \
            --with-systemdtmpfilesdir=            \
            --with-systemdsystemunitdir=

make

if tup_tests_enabled "man-db"; then
make check
else tup_receipt_skip_tests "man-db"; fi

make install
