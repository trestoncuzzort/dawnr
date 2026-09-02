#!/bin/bash
# OVERRIDE ch05/gcc-libstdc++: the page title ("Libstdc++ from
# GCC-15.2.0") names no tarball of its own, so the driver's automatic wrapping
# cannot fire; this override does the book's prose instruction (build from the
# freshly re-extracted GCC tree) and then runs the page's own blocks verbatim.
set -e
cd $LFS/sources
GCC_TAR=$(ls gcc-*.tar.xz | head -1)
DIR=${GCC_TAR%.tar.xz}
rm -rf "$DIR"; tar xf "$GCC_TAR"; cd "$DIR"
sed '1,/^# TUP_ACTION_PAGE$/d' "$TUP_PAGE" > /tmp/libstdcxx-blocks.sh
bash -e /tmp/libstdcxx-blocks.sh
cd $LFS/sources && rm -rf "$DIR"
