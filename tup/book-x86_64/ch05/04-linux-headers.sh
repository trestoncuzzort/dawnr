# 5.4. Linux-6.16.1 API Headers
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter05/linux-headers.html
# TUP_TARBALL=linux-6.16.1.tar.xz

make mrproper

make headers
find usr/include -type f ! -name '*.h' -delete
cp -rv usr/include $LFS/usr
