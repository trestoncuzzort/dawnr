# 6.16. Xz-5.8.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/xz.html
# TUP_TARBALL=xz-5.8.1.tar.xz

./configure --prefix=/usr                     \
            --host=$LFS_TGT                   \
            --build=$(build-aux/config.guess) \
            --disable-static                  \
            --docdir=/usr/share/doc/xz-5.8.1

make

make DESTDIR=$LFS install

rm -v $LFS/usr/lib/liblzma.la
