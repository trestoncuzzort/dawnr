#!/bin/bash
# 8.68. Kbd-2.10.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/kbd.html
# TUP_TARBALL=kbd-2.10.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/68-kbd.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_3c30d86310d877c65217b6b457c096110577a7fd808c333587e08c4f875f0543'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../kbd-2.10.0-backspace-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed -i '/RESIZECONS_PROGS=/s/yes/no/' configure
sed -i 's/resizecons.8 //' docs/man/man8/Makefile.in
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
./configure --prefix=/usr --disable-vlock
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

if tup_tests_enabled "kbd"; then
# TUP_BLOCK_BEGIN=005
make check
# TUP_BLOCK_END=005
else tup_receipt_skip_tests "ch08/68-kbd.sh:block-005"; fi

# TUP_BLOCK_BEGIN=006
make install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cp -R -v docs/doc -T /usr/share/doc/kbd-2.10.0
# TUP_BLOCK_END=007
TUP_UNSELECTED_3c30d86310d877c65217b6b457c096110577a7fd808c333587e08c4f875f0543
