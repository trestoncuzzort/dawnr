#!/bin/bash
# 6.3. Ncurses-6.6
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/ncurses.html
# TUP_TARBALL=ncurses-6.6.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/03-ncurses.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_1e77afffe4ceb48e70cc185123fdf7ddbff436cd8d77bc82e831f54620fabc91'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir build
pushd build
  ../configure --prefix=$LFS/tools AWK=gawk
  make -C include
  make -C progs tic
  install progs/tic $LFS/tools/bin
popd
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr                \
            --host=$LFS_TGT              \
            --build=$(./config.guess)    \
            --mandir=/usr/share/man      \
            --with-manpage-format=normal \
            --with-shared                \
            --without-normal             \
            --with-cxx-shared            \
            --without-debug              \
            --without-ada                \
            --disable-stripping          \
            AWK=gawk
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make DESTDIR=$LFS install
ln -sv libncursesw.so $LFS/usr/lib/libncurses.so
sed -e 's/^#if.*XOPEN.*$/#if 1/' \
    -i $LFS/usr/include/curses.h
# TUP_BLOCK_END=004
TUP_UNSELECTED_1e77afffe4ceb48e70cc185123fdf7ddbff436cd8d77bc82e831f54620fabc91
