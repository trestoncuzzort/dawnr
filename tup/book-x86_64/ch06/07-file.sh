# 6.7. File-5.46
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter06/file.html
# TUP_TARBALL=file-5.46.tar.gz

mkdir build
pushd build
  ../configure --disable-bzlib      \
               --disable-libseccomp \
               --disable-xzlib      \
               --disable-zlib
  make
popd

./configure --prefix=/usr --host=$LFS_TGT --build=$(./config.guess)

make FILE_COMPILE=$(pwd)/build/src/file

make DESTDIR=$LFS install

rm -v $LFS/usr/lib/libmagic.la
