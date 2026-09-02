# 8.67. Kbd-2.8.0
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/kbd.html
# TUP_TARBALL=kbd-2.8.0.tar.xz

patch -Np1 -i ../kbd-2.8.0-backspace-1.patch

sed -i '/RESIZECONS_PROGS=/s/yes/no/' configure
sed -i 's/resizecons.8 //' docs/man/man8/Makefile.in

./configure --prefix=/usr --disable-vlock

make

make install

cp -R -v docs/doc -T /usr/share/doc/kbd-2.8.0
