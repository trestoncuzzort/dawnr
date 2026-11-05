#!/bin/bash
# TUP_TARBALL=libnftnl-1.3.2.tar.xz
# Upstream configure and tests/Makefile.am define this library's 32 tests.
source /tup-layer/common.sh
./configure --prefix=/usr --disable-static
make -j"$TUP_JOBS"
result=0
make -j1 check || result=$?
[ ! -f tests/test-suite.log ] || cp tests/test-suite.log /sources/log/libnftnl-upstream.log
[ "$result" -eq 0 ] || exit "$result"
make install
