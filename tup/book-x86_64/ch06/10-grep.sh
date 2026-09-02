# 6.10. Grep-3.12
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/grep.html
# TUP_TARBALL=grep-3.12.tar.xz

./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(./build-aux/config.guess)

make

make DESTDIR=$LFS install
