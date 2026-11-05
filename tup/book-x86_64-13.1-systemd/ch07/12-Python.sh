#!/bin/bash
# 7.12. Python-3.14.7
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/Python.html
# TUP_TARBALL=Python-3.14.7.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/12-Python.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a26325f6fa747eda4d23b7cbed2d8f38d3263711eea1f70e26840521fc763098'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr       \
            --enable-shared     \
            --without-ensurepip \
            --without-static-libpython
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_a26325f6fa747eda4d23b7cbed2d8f38d3263711eea1f70e26840521fc763098
