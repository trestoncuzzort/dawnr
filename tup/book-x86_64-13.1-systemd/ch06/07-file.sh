#!/bin/bash
# 6.7. File-5.48
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/file.html
# TUP_TARBALL=file-5.48.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/07-file.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_f35aff01a11fb185049c7012ef12bae180799043a34dde849673d67e841bb0a9'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir build
pushd build
  ../configure --disable-bzlib      \
               --disable-libseccomp \
               --disable-xzlib      \
               --disable-zlib
  make
popd
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr --host=$LFS_TGT --build=$(./config.guess)
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make FILE_COMPILE=$(pwd)/build/src/file
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make DESTDIR=$LFS install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
rm -v $LFS/usr/lib/libmagic.la
# TUP_BLOCK_END=005
TUP_UNSELECTED_f35aff01a11fb185049c7012ef12bae180799043a34dde849673d67e841bb0a9
