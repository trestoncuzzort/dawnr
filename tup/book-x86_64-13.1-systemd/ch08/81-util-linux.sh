#!/bin/bash
# 8.81. Util-linux-2.42.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/util-linux.html
# TUP_TARBALL=util-linux-2.42.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/81-util-linux.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_9265741e66efb44f59ebb02ba130de1ab348c1e4d8fde8e4dfa89b9149dc3ea9'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
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
            ADJTIME_PATH=/var/lib/hwclock/adjtime \
            --docdir=/usr/share/doc/util-linux-2.42.2
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
bash tests/run.sh --srcdir=$PWD --builddir=$PWD
# TUP_BLOCK_END=003

if tup_tests_enabled "util-linux"; then
# TUP_BLOCK_BEGIN=004
touch /etc/fstab
chown -R tester .
su tester -c "make -k check"
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/81-util-linux.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005
TUP_UNSELECTED_9265741e66efb44f59ebb02ba130de1ab348c1e4d8fde8e4dfa89b9149dc3ea9
