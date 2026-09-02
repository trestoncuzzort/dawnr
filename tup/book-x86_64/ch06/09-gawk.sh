# 6.9. Gawk-5.3.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/gawk.html
# TUP_TARBALL=gawk-5.3.2.tar.xz

sed -i 's/extras//' Makefile.in

./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)

make

make DESTDIR=$LFS install
