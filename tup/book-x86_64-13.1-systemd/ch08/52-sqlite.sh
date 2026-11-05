#!/bin/bash
# 8.52. Sqlite-3530400
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/sqlite.html
# TUP_TARBALL=sqlite-autoconf-3530400.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/52-sqlite.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_1b6408b2dfc681f4d76ce31b65dbca5aca71d731199fe8f00cd61fdf61be9af7'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
python3 -m zipfile -e ../sqlite-doc-3530400.zip .
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr     \
            --disable-static  \
            --enable-fts{4,5} \
            CPPFLAGS="-D SQLITE_ENABLE_COLUMN_METADATA=1 \
                      -D SQLITE_ENABLE_UNLOCK_NOTIFY=1   \
                      -D SQLITE_ENABLE_DBSTAT_VTAB=1     \
                      -D SQLITE_SECURE_DELETE=1"
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make LDFLAGS.rpath=""
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
cp -v -R sqlite-doc-3530400 -T /usr/share/doc/sqlite-3.53.4
# TUP_BLOCK_END=005
TUP_UNSELECTED_1b6408b2dfc681f4d76ce31b65dbca5aca71d731199fe8f00cd61fdf61be9af7
