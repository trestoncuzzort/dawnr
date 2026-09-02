# 5.2. Binutils-2.45 - Pass 1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter05/binutils-pass1.html
# TUP_TARBALL=binutils-2.45.tar.xz

mkdir -v build
cd       build

../configure --prefix=$LFS/tools \
             --with-sysroot=$LFS \
             --target=$LFS_TGT   \
             --disable-nls       \
             --enable-gprofng=no \
             --disable-werror    \
             --enable-new-dtags  \
             --enable-default-hash-style=gnu

make

make install
