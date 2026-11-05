#!/bin/bash
# 5.3. GCC-16.2.0 - Pass 1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter05/gcc-pass1.html
# TUP_TARBALL=gcc-16.2.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch05/03-gcc-pass1.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_95c38c057c6762c891411a0ca5b10647537463e3cd9ca4c3b16f9918b50dacc0'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
tar -xf ../mpfr-4.2.2.tar.xz
mv -v mpfr-4.2.2 mpfr
tar -xf ../gmp-6.3.0.tar.xz
mv -v gmp-6.3.0 gmp
tar -xf ../mpc-1.4.1.tar.xz
mv -v mpc-1.4.1 mpc
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
case $(uname -m) in
  x86_64)
    sed -e '/m64=/s/lib64/lib/' \
        -i.orig gcc/config/i386/t-linux64
 ;;
esac
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
mkdir -v build
cd       build
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
../configure                  \
    --target=$LFS_TGT         \
    --prefix=$LFS/tools       \
    --with-glibc-version=2.44 \
    --with-sysroot=$LFS       \
    --with-newlib             \
    --without-headers         \
    --enable-default-pie      \
    --enable-default-ssp      \
    --disable-fixincludes     \
    --disable-nls             \
    --disable-shared          \
    --disable-multilib        \
    --disable-threads         \
    --disable-libatomic       \
    --disable-libgomp         \
    --disable-libquadmath     \
    --disable-libssp          \
    --disable-libvtv          \
    --disable-libstdcxx       \
    --enable-languages=c,c++
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cat ../gcc/{limitx,glimits,limity}.h  > \
  $($LFS_TGT-gcc -print-file-name=include)/limits.h
# TUP_BLOCK_END=007
TUP_UNSELECTED_95c38c057c6762c891411a0ca5b10647537463e3cd9ca4c3b16f9918b50dacc0
