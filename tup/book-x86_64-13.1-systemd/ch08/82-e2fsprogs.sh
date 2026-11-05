#!/bin/bash
# 8.82. E2fsprogs-1.47.4
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/e2fsprogs.html
# TUP_TARBALL=e2fsprogs-1.47.4.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/82-e2fsprogs.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_d1294be3861b67bf2b5bbc7954d240bf4dbad6eac7e9fd4e423d8f438702e78e'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -v build
cd       build
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
../configure --prefix=/usr       \
             --sysconfdir=/etc   \
             --enable-elf-shlibs \
             --disable-libblkid  \
             --disable-libuuid   \
             --disable-uuidd     \
             --disable-fsck
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "e2fsprogs"; then
# TUP_BLOCK_BEGIN=004
make check
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/82-e2fsprogs.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
rm -fv /usr/lib/{libcom_err,libe2p,libext2fs,libss}.a
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
gunzip -v /usr/share/info/libext2fs.info.gz
install-info --dir-file=/usr/share/info/dir /usr/share/info/libext2fs.info
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
makeinfo -o      doc/com_err.info ../lib/et/com_err.texinfo
install -v -m644 doc/com_err.info /usr/share/info
install-info --dir-file=/usr/share/info/dir /usr/share/info/com_err.info
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
sed 's/metadata_csum_seed,//' -i /etc/mke2fs.conf
# TUP_BLOCK_END=009
TUP_UNSELECTED_d1294be3861b67bf2b5bbc7954d240bf4dbad6eac7e9fd4e423d8f438702e78e
