# 8.12. Readline-8.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/readline.html
# TUP_TARBALL=readline-8.3.tar.gz

sed -i '/MV.*old/d' Makefile.in
sed -i '/{OLDSUFF}/c:' support/shlib-install

sed -i 's/-Wl,-rpath,[^ ]*//' support/shobj-conf

./configure --prefix=/usr    \
            --disable-static \
            --with-curses    \
            --docdir=/usr/share/doc/readline-8.3

make SHLIB_LIBS="-lncursesw"

make install

install -v -m644 doc/*.{ps,pdf,html,dvi} /usr/share/doc/readline-8.3
