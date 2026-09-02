# 8.80. E2fsprogs-1.47.3
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/e2fsprogs.html
# TUP_TARBALL=e2fsprogs-1.47.3.tar.gz

mkdir -v build
cd       build

../configure --prefix=/usr       \
             --sysconfdir=/etc   \
             --enable-elf-shlibs \
             --disable-libblkid  \
             --disable-libuuid   \
             --disable-uuidd     \
             --disable-fsck

make

if tup_tests_enabled "e2fsprogs"; then
make check
else tup_receipt_skip_tests "e2fsprogs"; fi

make install

rm -fv /usr/lib/{libcom_err,libe2p,libext2fs,libss}.a

gunzip -v /usr/share/info/libext2fs.info.gz
install-info --dir-file=/usr/share/info/dir /usr/share/info/libext2fs.info

makeinfo -o      doc/com_err.info ../lib/et/com_err.texinfo
install -v -m644 doc/com_err.info /usr/share/info
install-info --dir-file=/usr/share/info/dir /usr/share/info/com_err.info

sed 's/metadata_csum_seed,//' -i /etc/mke2fs.conf
