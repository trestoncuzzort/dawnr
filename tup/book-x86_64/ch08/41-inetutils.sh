# 8.41. Inetutils-2.6
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/inetutils.html
# TUP_TARBALL=inetutils-2.6.tar.xz

sed -i 's/def HAVE_TERMCAP_TGETENT/ 1/' telnet/telnet.c

./configure --prefix=/usr        \
            --bindir=/usr/bin    \
            --localstatedir=/var \
            --disable-logger     \
            --disable-whois      \
            --disable-rcp        \
            --disable-rexec      \
            --disable-rlogin     \
            --disable-rsh        \
            --disable-servers

make

if tup_tests_enabled "inetutils"; then
make check
else tup_receipt_skip_tests "inetutils"; fi

make install

mv -v /usr/{,s}bin/ifconfig
