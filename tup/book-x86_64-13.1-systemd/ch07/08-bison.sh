#!/bin/bash
# 7.8. Bison-3.8.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/bison.html
# TUP_TARBALL=bison-3.8.2.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/08-bison.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_db1d5adf078da8c12c3de9474232d705fd1a62f50547cf8a9238b674bbb95d12'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr \
            --docdir=/usr/share/doc/bison-3.8.2
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_db1d5adf078da8c12c3de9474232d705fd1a62f50547cf8a9238b674bbb95d12
