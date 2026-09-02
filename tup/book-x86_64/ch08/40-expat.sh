# 8.40. Expat-2.7.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/expat.html
# TUP_TARBALL=expat-2.7.1.tar.xz

./configure --prefix=/usr    \
            --disable-static \
            --docdir=/usr/share/doc/expat-2.7.1

make

if tup_tests_enabled "expat"; then
make check
else tup_receipt_skip_tests "expat"; fi

make install

install -v -m644 doc/*.{html,css} /usr/share/doc/expat-2.7.1
