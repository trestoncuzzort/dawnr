#!/bin/bash
# 8.12. Readline-8.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/readline.html
# TUP_TARBALL=readline-8.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/12-readline.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_6d423e58c1f8631a638e57fdfef680ab877207ff040683a432a2b39a88222505'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i '/MV.*old/d' Makefile.in
sed -i '/{OLDSUFF}/c:' support/shlib-install
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sed -i 's/-Wl,-rpath,[^ ]*//' support/shobj-conf
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
sed -e '270a\
     else\
       chars_avail = 1;'      \
    -e '288i\   result = -1;' \
    -i.orig input.c
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
./configure --prefix=/usr    \
            --disable-static \
            --with-curses    \
            --docdir=/usr/share/doc/readline-8.3
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make SHLIB_LIBS="-lncursesw"
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
make install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
install -v -m644 doc/*.{ps,pdf,html,dvi} /usr/share/doc/readline-8.3
# TUP_BLOCK_END=007
TUP_UNSELECTED_6d423e58c1f8631a638e57fdfef680ab877207ff040683a432a2b39a88222505
