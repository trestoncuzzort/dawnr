# 8.82. SysVinit-3.14
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/sysvinit.html
# TUP_TARBALL=sysvinit-3.14.tar.xz

patch -Np1 -i ../sysvinit-3.14-consolidated-1.patch

make

make install
