# 8.3. Man-pages-6.15
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/man-pages.html
# TUP_TARBALL=man-pages-6.15.tar.xz

rm -v man3/crypt*

make -R GIT=false prefix=/usr install
