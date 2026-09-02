# 8.2. Package Management
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/pkgmgt.html
# TUP_ACTION_PAGE

grep -l 'libfoo.*deleted' /proc/*/maps | tr -cd 0-9\\n | xargs -r ps u   || true   # advisory: see extract_book.py

./configure --prefix=/usr/pkg/libfoo/1.1
make
make install

./configure --prefix=/usr
make
make DESTDIR=/usr/pkg/libfoo/1.1 install
