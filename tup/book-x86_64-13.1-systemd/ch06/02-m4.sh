#!/bin/bash
# 6.2. M4-1.4.21
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/m4.html
# TUP_TARBALL=m4-1.4.21.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/02-m4.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_b0e328d6b0e3678cee4a371d697dee6c76b73e9799171959317620d58066cbb3'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cat > $LFS/usr/share/config.site << EOF
ac_cv_func_posix_spawn_file_actions_addchdir=yes
ac_cv_func_posix_spawn_file_actions_addfchdir=yes
EOF
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr   \
            --host=$LFS_TGT \
            --build=$(build-aux/config.guess)
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
make DESTDIR=$LFS install
# TUP_BLOCK_END=004
TUP_UNSELECTED_b0e328d6b0e3678cee4a371d697dee6c76b73e9799171959317620d58066cbb3
