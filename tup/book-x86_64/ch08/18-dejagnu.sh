# 8.18. DejaGNU-1.6.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/dejagnu.html
# TUP_TARBALL=dejagnu-1.6.3.tar.gz

mkdir -v build
cd       build

../configure --prefix=/usr
makeinfo --html --no-split -o doc/dejagnu.html ../doc/dejagnu.texi
makeinfo --plaintext       -o doc/dejagnu.txt  ../doc/dejagnu.texi

if tup_tests_enabled "dejagnu"; then
make check
else tup_receipt_skip_tests "dejagnu"; fi

make install
install -v -dm755  /usr/share/doc/dejagnu-1.6.3
install -v -m644   doc/dejagnu.{html,txt} /usr/share/doc/dejagnu-1.6.3
