#!/bin/bash
# 8.61. Coreutils-9.11
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/coreutils.html
# TUP_TARBALL=coreutils-9.11.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/61-coreutils.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_ff0858c1626ab7097a8dce47ae021d3fb53c1fc8c7ddae02efea8da947b52a72'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../coreutils-9.11-i18n-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
autoreconf -fv
automake -af
FORCE_UNSAFE_CONFIGURE=1 ./configure \
            --prefix=/usr
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "coreutils"; then
# TUP_BLOCK_BEGIN=004
make NON_ROOT_USERNAME=tester check-root
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/61-coreutils.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
groupadd -g 102 dummy -U tester
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
chown -R tester . 
# TUP_BLOCK_END=006

if tup_tests_enabled "coreutils"; then
# TUP_BLOCK_BEGIN=007
su tester -c "PATH=$PATH make -k RUN_EXPENSIVE_TESTS=yes check" \
   < /dev/null
# TUP_BLOCK_END=007
else tup_receipt_skip_tests "ch08/61-coreutils.sh:block-007"; fi

# TUP_BLOCK_BEGIN=008
groupdel dummy
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
make install
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
mv -v /usr/bin/chroot /usr/sbin
mv -v /usr/share/man/man1/chroot.1 /usr/share/man/man8/chroot.8
sed -i 's/"1"/"8"/' /usr/share/man/man8/chroot.8
# TUP_BLOCK_END=010
TUP_UNSELECTED_ff0858c1626ab7097a8dce47ae021d3fb53c1fc8c7ddae02efea8da947b52a72
