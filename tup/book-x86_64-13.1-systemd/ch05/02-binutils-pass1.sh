#!/bin/bash
# 5.2. Binutils-2.47 - Pass 1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter05/binutils-pass1.html
# TUP_TARBALL=binutils-2.47.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch05/02-binutils-pass1.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_3574bffb7b3fb211ab18d7bf389a2aee952257df637e266eb2bc6fde840ef30b'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -v build
cd       build
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
../configure --prefix=$LFS/tools \
             --with-sysroot=$LFS \
             --target=$LFS_TGT   \
             --disable-nls       \
             --enable-gprofng=no \
             --disable-werror    \
             --enable-new-dtags  \
             --enable-default-hash-style=gnu
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_3574bffb7b3fb211ab18d7bf389a2aee952257df637e266eb2bc6fde840ef30b
