#!/bin/bash
# 6.5. Coreutils-9.11
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter06/coreutils.html
# TUP_TARBALL=coreutils-9.11.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch06/05-coreutils.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_4386062e02cd3c53b06c1581e2c43772212163eb77fcdcd630c957261c406387'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                     \
            --host=$LFS_TGT                   \
            --build=$(build-aux/config.guess) \
            --enable-install-program=hostname
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make DESTDIR=$LFS install
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
mv -v $LFS/usr/bin/chroot              $LFS/usr/sbin
mkdir -pv $LFS/usr/share/man/man8
mv -v $LFS/usr/share/man/man1/chroot.1 $LFS/usr/share/man/man8/chroot.8
sed -i 's/"1"/"8"/'                    $LFS/usr/share/man/man8/chroot.8
# TUP_BLOCK_END=004
TUP_UNSELECTED_4386062e02cd3c53b06c1581e2c43772212163eb77fcdcd630c957261c406387
