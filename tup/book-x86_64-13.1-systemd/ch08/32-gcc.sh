#!/bin/bash
# 8.32. GCC-16.2.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gcc.html
# TUP_TARBALL=gcc-16.2.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/32-gcc.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_55614d6959bad433482874d3d914be199c7f213b675f9c10430aa2ef3619b08c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
case $(uname -m) in
  x86_64)
    sed -e '/m64=/s/lib64/lib/' \
        -i.orig gcc/config/i386/t-linux64
  ;;
esac
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mkdir -v build
cd       build
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
../configure --prefix=/usr            \
             LD=ld                    \
             --enable-languages=c,c++ \
             --enable-default-pie     \
             --enable-default-ssp     \
             --enable-host-pie        \
             --enable-targets=all     \
             --disable-multilib       \
             --disable-bootstrap      \
             --disable-fixincludes    \
             --with-system-zlib
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
ulimit -s -H unlimited
# TUP_BLOCK_END=005

if tup_tests_enabled "gcc"; then
# TUP_BLOCK_BEGIN=006
chown -R tester .
su tester -c "PATH=$PATH make -k check"
# TUP_BLOCK_END=006
else tup_receipt_skip_tests "ch08/32-gcc.sh:block-006"; fi

# TUP_BLOCK_BEGIN=007
../contrib/test_summary -t
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
make install
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
chown -v -R root:root $(gcc -print-file-name=include){,-fixed}
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
ln -svr /usr/bin/cpp /usr/lib
# TUP_BLOCK_END=010

# TUP_BLOCK_BEGIN=011
ln -sv gcc.1 /usr/share/man/man1/cc.1
# TUP_BLOCK_END=011

# TUP_BLOCK_BEGIN=012
ln -sfvr $(gcc -print-prog-name=liblto_plugin.so) /usr/lib/bfd-plugins/
# TUP_BLOCK_END=012

# TUP_BLOCK_BEGIN=013
echo 'int main(){}' | cc -x c - -v -Wl,--verbose &> dummy.log
readelf -l a.out | grep ': /lib'
# TUP_BLOCK_END=013

# TUP_BLOCK_BEGIN=014
grep -E -o '/usr/lib.*/S?crt[1in].*succeeded' dummy.log
# TUP_BLOCK_END=014

# TUP_BLOCK_BEGIN=015
grep -B4 '^ /usr/include' dummy.log
# TUP_BLOCK_END=015

# TUP_BLOCK_BEGIN=016
grep 'SEARCH.*/usr/lib' dummy.log |sed 's|; |\n|g'
# TUP_BLOCK_END=016

# TUP_BLOCK_BEGIN=017
grep "/lib.*/libc.so.6 " dummy.log
# TUP_BLOCK_END=017

# TUP_BLOCK_BEGIN=018
grep found dummy.log
# TUP_BLOCK_END=018

# TUP_BLOCK_BEGIN=019
rm -v a.out dummy.log
# TUP_BLOCK_END=019

# TUP_BLOCK_BEGIN=020
mkdir -pv /usr/share/gdb/auto-load/usr/lib
mv -v /usr/lib/*gdb.py /usr/share/gdb/auto-load/usr/lib
# TUP_BLOCK_END=020
TUP_UNSELECTED_55614d6959bad433482874d3d914be199c7f213b675f9c10430aa2ef3619b08c
