#!/bin/bash
# 8.39. Bash-5.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/bash.html
# TUP_TARBALL=bash-5.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/39-bash.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_947c07f997112eefd7bf738599dc3fe5101baaae9d6acb4c3bee8f0415eb7d02'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr             \
            --without-bash-malloc     \
            --with-installed-readline \
            --docdir=/usr/share/doc/bash-5.3
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
chown -R tester .
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
LC_ALL=C.UTF-8 su -s /usr/bin/expect tester << "EOF"
set timeout -1
spawn make tests
expect eof
lassign [wait] _ _ _ value
exit $value
EOF
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
exec /usr/bin/bash --login
# TUP_BLOCK_END=006
TUP_UNSELECTED_947c07f997112eefd7bf738599dc3fe5101baaae9d6acb4c3bee8f0415eb7d02
