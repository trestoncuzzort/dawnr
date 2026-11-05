#!/bin/bash
# 8.7. Bzip2-1.0.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/bzip2.html
# TUP_TARBALL=bzip2-1.0.8.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/07-bzip2.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_db784635a7e7149d11d0157a418a1170f149118bf2962fd55b4755de6f47966f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../bzip2-1.0.8-install_docs-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed -i 's@\(ln -s -f \)$(PREFIX)/bin/@\1@' Makefile
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
sed -i "s@(PREFIX)/man@(PREFIX)/share/man@g" Makefile
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make -f Makefile-libbz2_so
make clean
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make PREFIX=/usr install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cp -av libbz2.so.* /usr/lib
ln -sfv libbz2.so.1.0.8 /usr/lib/libbz2.so
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
ln -sfv libbz2.so.1.0.8 /usr/lib/libbz2.so.1
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
cp -v bzip2-shared /usr/bin/bzip2
for i in /usr/bin/{bzcat,bunzip2}; do
  ln -sfv bzip2 $i
done
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
rm -fv /usr/lib/libbz2.a
# TUP_BLOCK_END=010
TUP_UNSELECTED_db784635a7e7149d11d0157a418a1170f149118bf2962fd55b4755de6f47966f
