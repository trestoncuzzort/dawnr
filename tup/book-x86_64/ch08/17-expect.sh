# 8.17. Expect-5.45.4
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/expect.html
# TUP_TARBALL=expect5.45.4.tar.gz

python3 -c 'from pty import spawn; spawn(["echo", "ok"])'

patch -Np1 -i ../expect-5.45.4-gcc15-1.patch

./configure --prefix=/usr           \
            --with-tcl=/usr/lib     \
            --enable-shared         \
            --disable-rpath         \
            --mandir=/usr/share/man \
            --with-tclinclude=/usr/include

make

if tup_tests_enabled "expect"; then
make test
else tup_receipt_skip_tests "expect"; fi

make install
ln -svf expect5.45.4/libexpect5.45.4.so /usr/lib
