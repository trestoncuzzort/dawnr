# 6.11. Gzip-1.14
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/gzip.html
# TUP_TARBALL=gzip-1.14.tar.xz

./configure --prefix=/usr --host=$LFS_TGT

make

make DESTDIR=$LFS install
