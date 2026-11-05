#!/bin/bash
# 6.6. Diffutils-3.12
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/diffutils.html
# TUP_TARBALL=diffutils-3.12.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/06-diffutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a90572571bfc7f16787d74dbc030ca2c3f0758a4750d088c72f7a0a4e28b1a1a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            gl_cv_func_strcasecmp_works=yes \
            --build=$(./build-aux/config.guess)
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003
TUP_UNSELECTED_a90572571bfc7f16787d74dbc030ca2c3f0758a4750d088c72f7a0a4e28b1a1a
