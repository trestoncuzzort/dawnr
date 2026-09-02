# 6.15. Tar-1.35
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/tar.html
# TUP_TARBALL=tar-1.35.tar.xz

./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)

make

make DESTDIR=$LFS install
