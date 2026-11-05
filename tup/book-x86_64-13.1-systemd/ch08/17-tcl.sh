#!/bin/bash
# 8.17. Tcl-8.6.18
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/tcl.html
# TUP_TARBALL=tcl8.6.18-src.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/17-tcl.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_b9d2d98ce0ef124b901e05ca03faf7cbdc64cc58a7bdb774a7be76bafca39b4a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
SRCDIR=$(pwd)
cd unix
./configure --prefix=/usr           \
            --mandir=/usr/share/man \
            --disable-rpath
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make

sed -e "s|$SRCDIR/unix|/usr/lib|" \
    -e "s|$SRCDIR|/usr/include|"  \
    -i tclConfig.sh

sed -e "s|$SRCDIR/unix/pkgs/tdbc1.1.13|/usr/lib/tdbc1.1.13|" \
    -e "s|$SRCDIR/pkgs/tdbc1.1.13/generic|/usr/include|"     \
    -e "s|$SRCDIR/pkgs/tdbc1.1.13/library|/usr/lib/tcl8.6|"  \
    -e "s|$SRCDIR/pkgs/tdbc1.1.13|/usr/include|"             \
    -i pkgs/tdbc1.1.13/tdbcConfig.sh

sed -e "s|$SRCDIR/unix/pkgs/itcl4.3.7|/usr/lib/itcl4.3.7|" \
    -e "s|$SRCDIR/pkgs/itcl4.3.7/generic|/usr/include|"    \
    -e "s|$SRCDIR/pkgs/itcl4.3.7|/usr/include|"            \
    -i pkgs/itcl4.3.7/itclConfig.sh

unset SRCDIR
# TUP_BLOCK_END=002

if tup_tests_enabled "tcl"; then
# TUP_BLOCK_BEGIN=003
LC_ALL=C.UTF-8 make test
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/17-tcl.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install 
chmod 644 /usr/lib/libtclstub8.6.a
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
chmod -v u+w /usr/lib/libtcl8.6.so
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make install-private-headers
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
ln -sfv tclsh8.6 /usr/bin/tclsh
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
mv -v /usr/share/man/man3/{Thread,Tcl_Thread}.3
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
cd ..
tar -xf ../tcl8.6.18-html.tar.gz --strip-components=1
mkdir -v -p /usr/share/doc/tcl-8.6.18
cp -v -r  ./html/* /usr/share/doc/tcl-8.6.18
# TUP_BLOCK_END=009
TUP_UNSELECTED_b9d2d98ce0ef124b901e05ca03faf7cbdc64cc58a7bdb774a7be76bafca39b4a
