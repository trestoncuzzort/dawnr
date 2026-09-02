# 8.59. Coreutils-9.7
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/coreutils.html
# TUP_TARBALL=coreutils-9.7.tar.xz

patch -Np1 -i ../coreutils-9.7-upstream_fix-1.patch

patch -Np1 -i ../coreutils-9.7-i18n-1.patch

autoreconf -fv
automake -af
FORCE_UNSAFE_CONFIGURE=1 ./configure \
            --prefix=/usr            \
            --enable-no-install-program=kill,uptime

make

if tup_tests_enabled "coreutils"; then
make NON_ROOT_USERNAME=tester check-root
else tup_receipt_skip_tests "coreutils"; fi

groupadd -g 102 dummy -U tester

chown -R tester .

if tup_tests_enabled "coreutils"; then
su tester -c "PATH=$PATH make -k RUN_EXPENSIVE_TESTS=yes check" \
   < /dev/null
else tup_receipt_skip_tests "coreutils"; fi

groupdel dummy

make install

mv -v /usr/bin/chroot /usr/sbin
mv -v /usr/share/man/man1/chroot.1 /usr/share/man/man8/chroot.8
sed -i 's/"1"/"8"/' /usr/share/man/man8/chroot.8
