#!/bin/bash
# 5.6. Libstdc++ from GCC-16.2.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter05/gcc-libstdc++.html
# TUP_TARBALL=gcc-16.2.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch05/06-gcc-libstdc++.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_469dffcb91b9f39d058824dcc7b290245dbf13202349e90e203b30a8743ae544'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -v build
cd       build
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
../libstdc++-v3/configure      \
    --host=$LFS_TGT            \
    --build=$(../config.guess) \
    CXX=$LFS_TGT-gcc           \
    --prefix=/usr              \
    --disable-multilib         \
    --disable-nls              \
    --disable-libstdcxx-pch    \
    --with-gxx-include-dir=/tools/$LFS_TGT/include/c++/16.2.0
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make DESTDIR=$LFS install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
rm -v $LFS/usr/lib/lib{stdc++{,exp,fs},supc++}.la
# TUP_BLOCK_END=005
TUP_UNSELECTED_469dffcb91b9f39d058824dcc7b290245dbf13202349e90e203b30a8743ae544
