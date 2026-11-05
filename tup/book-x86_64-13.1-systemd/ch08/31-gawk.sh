#!/bin/bash
# 8.31. Gawk-5.4.1
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gawk.html
# TUP_TARBALL=gawk-5.4.1.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/31-gawk.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_96b9c07c08e48f55f08a647584ea6ac7f0ff23462902ebb3175295599fb4124c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i 's/extras//' Makefile.in
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "gawk"; then
# TUP_BLOCK_BEGIN=004
chown -R tester .
su tester -c "PATH=$PATH make check"
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/31-gawk.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
rm -f /usr/bin/gawk-5.4.1
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
ln -sv gawk.1 /usr/share/man/man1/awk.1
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
install -vDm644 doc/{awkforai.txt,*.{eps,pdf,jpg}} -t /usr/share/doc/gawk-5.4.1
# TUP_BLOCK_END=007
TUP_UNSELECTED_96b9c07c08e48f55f08a647584ea6ac7f0ff23462902ebb3175295599fb4124c
