# 7.10. Python-3.13.7
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/Python.html
# TUP_TARBALL=Python-3.13.7.tar.xz

./configure --prefix=/usr       \
            --enable-shared     \
            --without-ensurepip \
            --without-static-libpython

make

make install
