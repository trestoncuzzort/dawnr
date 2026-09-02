# 8.79. Util-linux-2.41.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/util-linux.html
# TUP_TARBALL=util-linux-2.41.1.tar.xz

./configure --bindir=/usr/bin     \
            --libdir=/usr/lib     \
            --runstatedir=/run    \
            --sbindir=/usr/sbin   \
            --disable-chfn-chsh   \
            --disable-login       \
            --disable-nologin     \
            --disable-su          \
            --disable-setpriv     \
            --disable-runuser     \
            --disable-pylibmount  \
            --disable-liblastlog2 \
            --disable-static      \
            --without-python      \
            --without-systemd     \
            --without-systemdsystemunitdir        \
            ADJTIME_PATH=/var/lib/hwclock/adjtime \
            --docdir=/usr/share/doc/util-linux-2.41.1

make

bash tests/run.sh --srcdir=$PWD --builddir=$PWD

if tup_tests_enabled "util-linux"; then
touch /etc/fstab
chown -R tester .
su tester -c "make -k check"
else tup_receipt_skip_tests "util-linux"; fi

make install
