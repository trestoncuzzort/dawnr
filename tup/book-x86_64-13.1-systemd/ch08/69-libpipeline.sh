#!/bin/bash
# 8.69. Libpipeline-1.5.8
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/libpipeline.html
# TUP_TARBALL=libpipeline-1.5.8.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/69-libpipeline.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_8cbab15868c43b3877d3a9bdb9d980b7a424c9dbb1baa08afc83477580365d35'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_8cbab15868c43b3877d3a9bdb9d980b7a424c9dbb1baa08afc83477580365d35
