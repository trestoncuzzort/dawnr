#!/bin/bash
# 8.42. Gperf-3.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/gperf.html
# TUP_TARBALL=gperf-3.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/42-gperf.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_9ea0ef6bc182cbdb903e2a9279eb8ca0fbccff40fb01cb5d196ea9a10acc23fc'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr --docdir=/usr/share/doc/gperf-3.3
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "gperf"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/42-gperf.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_9ea0ef6bc182cbdb903e2a9279eb8ca0fbccff40fb01cb5d196ea9a10acc23fc
