# 7.7. Gettext-0.26
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/gettext.html
# TUP_TARBALL=gettext-0.26.tar.xz

./configure --disable-shared

make

cp -v gettext-tools/src/{msgfmt,msgmerge,xgettext} /usr/bin
