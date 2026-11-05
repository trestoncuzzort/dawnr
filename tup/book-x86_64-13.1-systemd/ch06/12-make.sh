#!/bin/bash
# 6.12. Make-4.4.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/make.html
# TUP_TARBALL=make-4.4.1.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/12-make.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_62e00936835deae3b09f842c4ce6269c2415a029855ec74243509963bdc55dca'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_62e00936835deae3b09f842c4ce6269c2415a029855ec74243509963bdc55dca
