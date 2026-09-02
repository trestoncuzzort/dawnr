# 8.61. Gawk-5.3.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/gawk.html
# TUP_TARBALL=gawk-5.3.2.tar.xz

sed -i 's/extras//' Makefile.in

./configure --prefix=/usr

make

if tup_tests_enabled "gawk"; then
chown -R tester .
su tester -c "PATH=$PATH make check"
else tup_receipt_skip_tests "gawk"; fi

rm -f /usr/bin/gawk-5.3.2
make install

ln -sv gawk.1 /usr/share/man/man1/awk.1

install -vDm644 doc/{awkforai.txt,*.{eps,pdf,jpg}} -t /usr/share/doc/gawk-5.3.2
