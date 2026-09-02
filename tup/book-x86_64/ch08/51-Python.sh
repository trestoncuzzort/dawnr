# 8.51. Python-3.13.7
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/Python.html
# TUP_TARBALL=Python-3.13.7.tar.xz

./configure --prefix=/usr          \
            --enable-shared        \
            --with-system-expat    \
            --enable-optimizations \
            --without-static-libpython

make

if tup_tests_enabled "Python"; then
make test TESTOPTS="--timeout 120"
else tup_receipt_skip_tests "Python"; fi

make install

cat > /etc/pip.conf << EOF
[global]
root-user-action = ignore
disable-pip-version-check = true
EOF

install -v -dm755 /usr/share/doc/python-3.13.7/html

tar --strip-components=1  \
    --no-same-owner       \
    --no-same-permissions \
    -C /usr/share/doc/python-3.13.7/html \
    -xvf ../python-3.13.7-docs-html.tar.bz2
