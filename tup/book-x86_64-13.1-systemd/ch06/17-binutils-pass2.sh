#!/bin/bash
# 6.17. Binutils-2.47 - Pass 2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/binutils-pass2.html
# TUP_TARBALL=binutils-2.47.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/17-binutils-pass2.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_9836dca810a0e2b4d7626fc2b85aa0a0983b962c514f270f0c23a068cb9fecbf'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed '6031s/$add_dir//' -i ltmain.sh
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mkdir -v build
cd       build
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
../configure                   \
    --prefix=/usr              \
    --build=$(../config.guess) \
    --host=$LFS_TGT            \
    --disable-nls              \
    --enable-shared            \
    --enable-gprofng=no        \
    --disable-werror           \
    --enable-64-bit-bfd        \
    --enable-new-dtags         \
    --enable-default-hash-style=gnu
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make DESTDIR=$LFS install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
rm -v $LFS/usr/lib/lib{bfd,ctf,ctf-nobfd,opcodes,sframe}.{a,la}
# TUP_BLOCK_END=006
TUP_UNSELECTED_9836dca810a0e2b4d7626fc2b85aa0a0983b962c514f270f0c23a068cb9fecbf
