# 8.19. Pkgconf-2.5.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/pkgconf.html
# TUP_TARBALL=pkgconf-2.5.1.tar.xz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/pkgconf-2.5.1

make

make install

ln -sv pkgconf   /usr/bin/pkg-config
ln -sv pkgconf.1 /usr/share/man/man1/pkg-config.1
