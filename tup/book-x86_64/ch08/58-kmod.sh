# 8.58. Kmod-34.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/kmod.html
# TUP_TARBALL=kmod-34.2.tar.xz

mkdir -p build
cd       build

meson setup --prefix=/usr ..    \
            --buildtype=release \
            -D manpages=false

ninja

ninja install
