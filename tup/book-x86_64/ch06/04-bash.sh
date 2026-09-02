# 6.4. Bash-5.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/bash.html
# TUP_TARBALL=bash-5.3.tar.gz

./configure --prefix=/usr                      \
            --build=$(sh support/config.guess) \
            --host=$LFS_TGT                    \
            --without-bash-malloc

make

make DESTDIR=$LFS install

ln -sv bash $LFS/bin/sh
