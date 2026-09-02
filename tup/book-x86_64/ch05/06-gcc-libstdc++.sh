# 5.6. Libstdc++ from GCC-15.2.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter05/gcc-libstdc++.html
# TUP_TARBALL=gcc-15.2.0.tar.xz

mkdir -v build
cd       build

../libstdc++-v3/configure      \
    --host=$LFS_TGT            \
    --build=$(../config.guess) \
    --prefix=/usr              \
    --disable-multilib         \
    --disable-nls              \
    --disable-libstdcxx-pch    \
    --with-gxx-include-dir=/tools/$LFS_TGT/include/c++/15.2.0

make

make DESTDIR=$LFS install

rm -v $LFS/usr/lib/lib{stdc++{,exp,fs},supc++}.la
