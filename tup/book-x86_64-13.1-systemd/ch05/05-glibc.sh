#!/bin/bash
# 5.5. Glibc-2.44
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter05/glibc.html
# TUP_TARBALL=glibc-2.44.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch05/05-glibc.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_c7814d20e0896d36572220732853951c0d7418e85edf0c5bf7c796dd81ae40df'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
case $(uname -m) in
    i?86)   ln -sfv ld-linux.so.2 $LFS/lib/ld-lsb.so.3
    ;;
    x86_64) ln -sfv ../lib/ld-linux-x86-64.so.2 $LFS/lib64
            ln -sfv ../lib/ld-linux-x86-64.so.2 $LFS/lib64/ld-lsb-x86-64.so.3
    ;;
esac
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
patch -Np1 -i ../glibc-fhs-1.patch
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
patch -Np1 -i ../glibc-2.44-upstream_fixes-1.patch
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
mkdir -v build
cd       build
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
echo "rootsbindir=/usr/sbin" > configparms
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
../configure                             \
      --prefix=/usr                      \
      --host=$LFS_TGT                    \
      --build=$(../scripts/config.guess) \
      --disable-nscd                     \
      libc_cv_slibdir=/usr/lib           \
      --enable-kernel=5.10
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
make
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
make DESTDIR=$LFS install
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
sed '/RTLDLIST=/s@/usr@@g' -i $LFS/usr/bin/ldd
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
echo 'int main(){}' | $LFS_TGT-gcc -x c - -v -Wl,--verbose &> dummy.log
$LFS_TGT-readelf -l a.out | grep ': /lib'
# TUP_BLOCK_END=010

# TUP_BLOCK_BEGIN=011
grep -E -o "$LFS/lib.*/S?crt[1in].*succeeded" dummy.log
# TUP_BLOCK_END=011

# TUP_BLOCK_BEGIN=012
grep -B3 "^ $LFS/usr/include" dummy.log
# TUP_BLOCK_END=012

# TUP_BLOCK_BEGIN=013
grep 'SEARCH.*/usr/lib' dummy.log |sed 's|; |\n|g'
# TUP_BLOCK_END=013

# TUP_BLOCK_BEGIN=014
grep "/lib.*/libc.so.6 " dummy.log
# TUP_BLOCK_END=014

# TUP_BLOCK_BEGIN=015
grep found dummy.log
# TUP_BLOCK_END=015

# TUP_BLOCK_BEGIN=016
rm -v a.out dummy.log
# TUP_BLOCK_END=016
TUP_UNSELECTED_c7814d20e0896d36572220732853951c0d7418e85edf0c5bf7c796dd81ae40df
