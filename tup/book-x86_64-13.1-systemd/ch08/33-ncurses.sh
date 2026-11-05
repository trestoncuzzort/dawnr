#!/bin/bash
# 8.33. Ncurses-6.6
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/ncurses.html
# TUP_TARBALL=ncurses-6.6.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/33-ncurses.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_ed1027ff32f4e17044cab6c14fede358ea6e862dd7d2d6e028e10aa30496c864'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr           \
            --mandir=/usr/share/man \
            --with-shared           \
            --without-debug         \
            --without-normal        \
            --with-cxx-shared       \
            --enable-pc-files       \
            --with-pkg-config-libdir=/usr/lib/pkgconfig
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$PWD/dest install
sed -e 's/^#if.*XOPEN.*$/#if 1/' \
    -i dest/usr/include/curses.h
cp --remove-destination -av dest/* /
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
for lib in ncurses form panel menu ; do
    ln -sfv lib${lib}w.so /usr/lib/lib${lib}.so
    ln -sfv ${lib}w.pc    /usr/lib/pkgconfig/${lib}.pc
done
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
ln -sfv libncursesw.so /usr/lib/libcurses.so
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
cp -v -R doc -T /usr/share/doc/ncurses-6.6
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
make distclean
./configure --prefix=/usr    \
            --with-shared    \
            --without-normal \
            --without-debug  \
            --without-cxx-binding \
            --with-abi-version=5
make sources libs
cp -av lib/lib*.so.5* /usr/lib
# TUP_BLOCK_END=007
TUP_UNSELECTED_ed1027ff32f4e17044cab6c14fede358ea6e862dd7d2d6e028e10aa30496c864
