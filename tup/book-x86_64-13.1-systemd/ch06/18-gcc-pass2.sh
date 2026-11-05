#!/bin/bash
# 6.18. GCC-16.2.0 - Pass 2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/gcc-pass2.html
# TUP_TARBALL=gcc-16.2.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/18-gcc-pass2.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_02bcd67a99fbafb3748452d83d8883f5a62aa90a17318418337faf3115f6e9e2'
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
../configure                   \
    --build=$(../config.guess) \
    --host=$LFS_TGT            \
    --target=$LFS_TGT          \
    --prefix=/usr              \
    --with-build-sysroot=$LFS  \
    --enable-default-pie       \
    --enable-default-ssp       \
    --disable-fixincludes      \
    --disable-nls              \
    --disable-multilib         \
    --disable-libatomic        \
    --disable-libgomp          \
    --disable-libquadmath      \
    --disable-libsanitizer     \
    --disable-libssp           \
    --disable-libvtv           \
    --enable-languages=c,c++   \
    CXX_FOR_TARGET="$LFS_TGT-gcc -nostdinc++" \
    LDFLAGS_FOR_TARGET=-L$PWD/$LFS_TGT/libgcc \
    target_configargs=gcc_cv_target_thread_file=posix
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make DESTDIR=$LFS install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
ln -sv gcc $LFS/usr/bin/cc
# TUP_BLOCK_END=007
TUP_UNSELECTED_02bcd67a99fbafb3748452d83d8883f5a62aa90a17318418337faf3115f6e9e2
