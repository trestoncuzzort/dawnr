# 7.12. Util-linux-2.41.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/util-linux.html
# TUP_TARBALL=util-linux-2.41.1.tar.xz

mkdir -pv /var/lib/hwclock

./configure --libdir=/usr/lib     \
            --runstatedir=/run    \
            --disable-chfn-chsh   \
            --disable-login       \
            --disable-nologin     \
            --disable-su          \
            --disable-setpriv     \
            --disable-runuser     \
            --disable-pylibmount  \
            --disable-static      \
            --disable-liblastlog2 \
            --without-python      \
            ADJTIME_PATH=/var/lib/hwclock/adjtime \
            --docdir=/usr/share/doc/util-linux-2.41.1

make

make install
