#!/bin/bash
# 8.5. Glibc-2.44
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/glibc.html
# TUP_TARBALL=glibc-2.44.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch08/05-glibc.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_463fea4974020e9b3f70effb0c7dfd2d8a42d51997b269695a0c786158ad87f2'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
patch -Np1 -i ../glibc-fhs-1.patch
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
patch -Np1 -i ../glibc-2.44-upstream_fixes-1.patch
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
mkdir -v build
cd       build
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
../configure --prefix=/usr                   \
             --disable-werror                \
             --disable-nscd                  \
             libc_cv_slibdir=/usr/lib        \
             --enable-stack-protector=strong \
             --enable-kernel=5.10
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make
# TUP_BLOCK_END=005

if tup_tests_enabled "glibc"; then
# TUP_BLOCK_BEGIN=006
make check
# TUP_BLOCK_END=006
else tup_receipt_skip_tests "ch08/05-glibc.sh:block-006"; fi

# TUP_BLOCK_BEGIN=007
grep "Timed out" $(find -name \*.out)
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
touch /etc/ld.so.conf
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
sed '/test-installation/s@$(PERL)@echo not running@' -i ../Makefile
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
rm -f /usr/sbin/nscd
# TUP_BLOCK_END=010

# TUP_BLOCK_BEGIN=011
systemctl disable --now nscd
# TUP_BLOCK_END=011

# TUP_BLOCK_BEGIN=012
make DESTDIR=$PWD/dest install
install -vm755 dest/usr/lib/*.so.* /usr/lib
# TUP_BLOCK_END=012

# TUP_BLOCK_BEGIN=013
DIR=$(dirname $(gcc -print-libgcc-file-name))
[ -e $DIR/include/limits.h ]    || mv $DIR/include{-fixed,}/limits.h
[ -e $DIR/include/syslimits.h ] || mv $DIR/include{-fixed,}/syslimits.h
rm -rfv $DIR/include-fixed/*
unset DIR
# TUP_BLOCK_END=013

# TUP_BLOCK_BEGIN=014
make install
# TUP_BLOCK_END=014

# TUP_BLOCK_BEGIN=015
sed '/RTLDLIST=/s@/usr@@g' -i /usr/bin/ldd
# TUP_BLOCK_END=015

# TUP_BLOCK_BEGIN=016
localedef -i C -f UTF-8 C.UTF-8
localedef -i cs_CZ -f UTF-8 cs_CZ.UTF-8
localedef -i de_DE -f ISO-8859-1 de_DE
localedef -i de_DE@euro -f ISO-8859-15 de_DE@euro
localedef -i de_DE -f UTF-8 de_DE.UTF-8
localedef -i el_GR -f ISO-8859-7 el_GR
localedef -i en_GB -f ISO-8859-1 en_GB
localedef -i en_GB -f UTF-8 en_GB.UTF-8
localedef -i en_HK -f ISO-8859-1 en_HK
localedef -i en_PH -f ISO-8859-1 en_PH
localedef -i en_US -f ISO-8859-1 en_US
localedef -i en_US -f UTF-8 en_US.UTF-8
localedef -i es_ES -f ISO-8859-15 es_ES@euro
localedef -i es_MX -f ISO-8859-1 es_MX
localedef -i fa_IR -f UTF-8 fa_IR
localedef -i fr_FR -f ISO-8859-1 fr_FR
localedef -i fr_FR@euro -f ISO-8859-15 fr_FR@euro
localedef -i fr_FR -f UTF-8 fr_FR.UTF-8
localedef -i is_IS -f ISO-8859-1 is_IS
localedef -i is_IS -f UTF-8 is_IS.UTF-8
localedef -i it_IT -f ISO-8859-1 it_IT
localedef -i it_IT -f ISO-8859-15 it_IT@euro
localedef -i it_IT -f UTF-8 it_IT.UTF-8
localedef -i ja_JP -f EUC-JP ja_JP
localedef -i ja_JP -f UTF-8 ja_JP.UTF-8
localedef -i nl_NL@euro -f ISO-8859-15 nl_NL@euro
localedef -i ru_RU -f KOI8-R ru_RU.KOI8-R
localedef -i ru_RU -f UTF-8 ru_RU.UTF-8
localedef -i se_NO -f UTF-8 se_NO.UTF-8
localedef -i ta_IN -f UTF-8 ta_IN.UTF-8
localedef -i tr_TR -f UTF-8 tr_TR.UTF-8
localedef -i zh_CN -f GB18030 zh_CN.GB18030
localedef -i zh_HK -f BIG5-HKSCS zh_HK.BIG5-HKSCS
localedef -i zh_TW -f UTF-8 zh_TW.UTF-8
# TUP_BLOCK_END=016

# TUP_BLOCK_BEGIN=017
make localedata/install-locales
# TUP_BLOCK_END=017

# TUP_BLOCK_BEGIN=018
cat > /etc/nsswitch.conf << "EOF"
# Begin /etc/nsswitch.conf

passwd: files systemd
group: files systemd
shadow: files systemd

hosts: mymachines resolve [!UNAVAIL=return] files myhostname dns
networks: files

protocols: files
services: files
ethers: files
rpc: files

# End /etc/nsswitch.conf
EOF
# TUP_BLOCK_END=018

# TUP_BLOCK_BEGIN=019
tar -xf ../../tzdata2026c.tar.gz

ZONEINFO=/usr/share/zoneinfo
mkdir -pv $ZONEINFO/{posix,right}

for tz in etcetera southamerica northamerica europe africa antarctica  \
          asia australasia backward; do
    zic -L /dev/null   -d $ZONEINFO       ${tz}
    zic -L /dev/null   -d $ZONEINFO/posix ${tz}
    zic -L leapseconds -d $ZONEINFO/right ${tz}
done

cp -v zone.tab zone1970.tab iso3166.tab $ZONEINFO
zic -d $ZONEINFO -p America/New_York
unset ZONEINFO tz
# TUP_BLOCK_END=019

# TUP_BLOCK_BEGIN=020
tzselect
# TUP_BLOCK_END=020

# TUP_BLOCK_BEGIN=021
ln -sfv /usr/share/zoneinfo/<xxx> /etc/localtime
# TUP_BLOCK_END=021

# TUP_BLOCK_BEGIN=022
cat > /etc/ld.so.conf << "EOF"
# Begin /etc/ld.so.conf
/usr/local/lib
/opt/lib

EOF
# TUP_BLOCK_END=022

# TUP_BLOCK_BEGIN=023
cat >> /etc/ld.so.conf << "EOF"
# Add an include directory
include /etc/ld.so.conf.d/*.conf

EOF
mkdir -pv /etc/ld.so.conf.d
# TUP_BLOCK_END=023
TUP_UNSELECTED_463fea4974020e9b3f70effb0c7dfd2d8a42d51997b269695a0c786158ad87f2
