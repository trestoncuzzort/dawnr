#!/bin/bash
# 8.30. Shadow-4.20.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/shadow.html
# TUP_TARBALL=shadow-4.20.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/30-shadow.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_920af8c1417c5ef387eb13da4a6a6dfae6f569c2df3150e8f0ef729c57cc01cf'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
find man -name Makefile.in -exec sed -i 's/getspnam\.3 / /' {} \;
find man -name Makefile.in -exec sed -i 's/passwd\.5 / /'   {} \;
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed -e 's:#ENCRYPT_METHOD SHA512:ENCRYPT_METHOD YESCRYPT:' \
    -e 's:/var/spool/mail:/var/mail:'                      \
    -e '/PATH=/{s@/sbin:@@;s@/bin:@@}'                     \
    -i etc/login.defs
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
touch /usr/bin/passwd
./configure --sysconfdir=/etc   \
            --disable-static    \
            --with-{b,yes}crypt \
            --without-libbsd    \
            --disable-logind    \
            --with-group-name-max-length=32
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make exec_prefix=/usr install
make -C man install-man
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
pwconv
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
grpconv
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
mkdir -p /etc/default
useradd -D --gid 999
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
sed -i '/MAIL/s/yes/no/' /etc/default/useradd
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
touch /etc/sub{u,g}id
# TUP_BLOCK_END=010

# TUP_BLOCK_BEGIN=011
passwd root
# TUP_BLOCK_END=011
TUP_UNSELECTED_920af8c1417c5ef387eb13da4a6a6dfae6f569c2df3150e8f0ef729c57cc01cf
