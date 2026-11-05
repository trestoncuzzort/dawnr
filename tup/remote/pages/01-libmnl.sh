#!/bin/bash
# TUP_TARBALL=libmnl-1.0.5.tar.bz2
# Upstream release INSTALL and configure; LGPL-2.1-or-later library.
source /tup-layer/common.sh
./configure --prefix=/usr --disable-static
make -j"$TUP_JOBS"
# Upstream libmnl has no make-check test suite; this is not a test pass.
printf '%s\n' 'libmnl: no upstream check suite; runtime use covered by libnftnl/nftables probes'
make install
