#!/bin/bash
# 8.18. Expect-5.45.4
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/expect.html
# TUP_TARBALL=expect5.45.4.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/18-expect.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_3e57782cb25c593240b213fdf5dbf4a56f7a634ad6f320e4cf537db7627a2369'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
python3 -c 'from pty import spawn; spawn(["echo", "ok"])'
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
patch -Np1 -i ../expect-5.45.4-gcc15-1.patch
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
./configure --prefix=/usr           \
            --with-tcl=/usr/lib     \
            --enable-shared         \
            --disable-rpath         \
            --mandir=/usr/share/man \
            --with-tclinclude=/usr/include
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

if tup_tests_enabled "expect"; then
# TUP_BLOCK_BEGIN=005
make test
# TUP_BLOCK_END=005
else tup_receipt_skip_tests "ch08/18-expect.sh:block-005"; fi

# TUP_BLOCK_BEGIN=006
make install
ln -svf expect5.45.4/libexpect5.45.4.so /usr/lib
# TUP_BLOCK_END=006
TUP_UNSELECTED_3e57782cb25c593240b213fdf5dbf4a56f7a634ad6f320e4cf537db7627a2369
