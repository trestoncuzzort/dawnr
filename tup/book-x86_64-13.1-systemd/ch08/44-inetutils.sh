#!/bin/bash
# 8.44. Inetutils-2.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/inetutils.html
# TUP_TARBALL=inetutils-2.8.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/44-inetutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_9e96d7d97b46581f6b03c09213d64af3625a4f7bd4ad21b05cb2791e68731761'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i 's/def HAVE_TERMCAP_TGETENT/ 1/' telnet/telnet.c
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
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
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "inetutils"; then
# TUP_BLOCK_BEGIN=004
make check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/44-inetutils.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
mv -v /usr/{,s}bin/ifconfig
# TUP_BLOCK_END=006
TUP_UNSELECTED_9e96d7d97b46581f6b03c09213d64af3625a4f7bd4ad21b05cb2791e68731761
