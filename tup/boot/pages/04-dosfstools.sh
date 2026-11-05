#!/bin/bash
# TUP_TARBALL=dosfstools-4.2.tar.gz
source /tup-layer/common.sh
# BLFS 13.1-systemd dosfstools recipe, options unchanged. tup/install/disk.py
# formats the EFI System Partition with the mkfs.fat this installs.
# https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/dosfstools.html
# Differences from the book, each deliberate:
#   xxd first          upstream's README: without xxd (vim) every test is
#                      skipped and "make check" still succeeds.
#   make -j1 check     serialized, its log retained and its summary required.
#   make -j1 install   serialized; the book's plain make inherits MAKEFLAGS.
command -v xxd > /dev/null || {
  echo 'xxd is missing: the dosfstools suite would skip every test' >&2; exit 1;
}
./configure --prefix=/usr --enable-compat-symlinks \
  --mandir=/usr/share/man --docdir=/usr/share/doc/dosfstools-4.2
make -j"$TUP_JOBS"
result=0
env LC_ALL=C make -j1 check > make-check.log 2>&1 || result=$?
cp make-check.log /sources/log/dosfstools-make-check.log
grep -E '^# [A-Z]+: ' make-check.log || true
[ "$result" -eq 0 ] || { tail -n 40 make-check.log >&2; exit "$result"; }
# Release 4.2 declares 40 tests (tests/Makefile.am), one of them, check-huge.fsck,
# an expected failure. Refuse a summary the exit status hid, a skipped suite
# and any other count.
for line in '# TOTAL: 40' '# PASS:  39' '# SKIP:  0' '# XFAIL: 1' '# FAIL:  0' '# XPASS: 0' '# ERROR: 0'; do
  grep -qx "$line" make-check.log || {
    echo "dosfstools upstream check summary lacks: $line" >&2; exit 1;
  }
done
make -j1 install
for name in mkfs.fat fsck.fat fatlabel; do
  [ -x "/usr/sbin/$name" ] && [ ! -L "/usr/sbin/$name" ] || {
    echo "dosfstools did not install /usr/sbin/$name" >&2; exit 1;
  }
done
for link in mkfs.vfat:mkfs.fat mkfs.msdos:mkfs.fat mkdosfs:mkfs.fat fsck.vfat:fsck.fat \
            fsck.msdos:fsck.fat dosfsck:fsck.fat dosfslabel:fatlabel; do
  [ "$(readlink "/usr/sbin/${link%%:*}")" = "${link##*:}" ] || {
    echo "dosfstools compatibility link is missing: ${link%%:*}" >&2; exit 1;
  }
done
# Installed-binary control with the installer's own options, on a regular file:
# the volume ID and label it asks for must be the ones blkid then reads, and
# the installed checker must accept the result without changing it.
/usr/sbin/mkfs.fat --help > mkfs-help.txt 2>&1 || true
grep -q '^mkfs.fat 4.2 ' mkfs-help.txt || {
  echo 'installed mkfs.fat does not report the selected version' >&2; exit 1;
}
truncate -s 64M control.img
/usr/sbin/mkfs.fat -F 32 -i 7C0FFEE5 -n TUP-ESP control.img
/usr/sbin/fsck.fat -n control.img
blkid -p -o export control.img > control.blkid
cat control.blkid
for line in TYPE=vfat VERSION=FAT32 UUID=7C0F-FEE5 LABEL=TUP-ESP; do
  grep -qx "$line" control.blkid || {
    echo "mkfs.fat control image lacks: $line" >&2; exit 1;
  }
done
printf '%s\n' 'dosfstools: 4.2 installed; 39 upstream tests passed, 1 expected failure; FAT32 control image verified'
