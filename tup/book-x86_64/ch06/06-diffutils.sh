# 6.6. Diffutils-3.12
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/diffutils.html
# TUP_TARBALL=diffutils-3.12.tar.xz

./configure --prefix=/usr   \
            --host=$LFS_TGT \
            gl_cv_func_strcasecmp_works=y \
            --build=$(./build-aux/config.guess)

make

make DESTDIR=$LFS install
