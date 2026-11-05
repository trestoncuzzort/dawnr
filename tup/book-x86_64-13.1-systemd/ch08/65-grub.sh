#!/bin/bash
# 8.65. GRUB-2.14
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grub.html
# TUP_TARBALL=grub-2.14.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/65-grub.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_2ac1d9a1e24fb711445084fe13f5190a746cd315457434ae82f8923e1eb0fb1a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
unset {C,CPP,CXX,LD}FLAGS
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed 's/--image-base/--nonexist-linker-option/' -i configure
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
./configure --prefix=/usr     \
            --sysconfdir=/etc \
            --disable-efiemu  \
            --disable-werror
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make clean
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
./configure --prefix=/usr       \
            --sysconfdir=/etc   \
            --target=x86_64     \
            --with-platform=efi \
            --disable-efiemu    \
            --disable-werror
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
make
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
make install
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
make clean
# TUP_BLOCK_END=010

# TUP_BLOCK_BEGIN=011
./configure --prefix=/usr       \
            --sysconfdir=/etc   \
            --target=i386       \
            --with-platform=efi \
            --disable-efiemu    \
            --disable-werror
# TUP_BLOCK_END=011

# TUP_BLOCK_BEGIN=012
make
# TUP_BLOCK_END=012

# TUP_BLOCK_BEGIN=013
make install
# TUP_BLOCK_END=013
TUP_UNSELECTED_2ac1d9a1e24fb711445084fe13f5190a746cd315457434ae82f8923e1eb0fb1a
