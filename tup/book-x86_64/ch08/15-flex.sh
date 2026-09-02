# 8.15. Flex-2.6.4
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/flex.html
# TUP_TARBALL=flex-2.6.4.tar.gz

./configure --prefix=/usr \
            --docdir=/usr/share/doc/flex-2.6.4 \
            --disable-static

make

if tup_tests_enabled "flex"; then
make check
else tup_receipt_skip_tests "flex"; fi

make install

ln -sv flex   /usr/bin/lex
ln -sv flex.1 /usr/share/man/man1/lex.1
