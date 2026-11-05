#!/bin/bash
# 6.9. Gawk-5.4.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/gawk.html
# TUP_TARBALL=gawk-5.4.1.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/09-gawk.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_134c2e404a43743e8d5cca9492ddf3e2533167fb2e874fc4d50128e73a24dca4'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i 's/extras//' Makefile.in
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make DESTDIR=$LFS install
# TUP_BLOCK_END=004
TUP_UNSELECTED_134c2e404a43743e8d5cca9492ddf3e2533167fb2e874fc4d50128e73a24dca4
