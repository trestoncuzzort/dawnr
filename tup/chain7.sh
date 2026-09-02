#!/bin/bash
# chain7.sh — the chroot crossing (runs as root). Waits for chapter 6, does the
# book's root-side pages (ownership, kernel filesystems), then enters chroot
# and hands pages 05-12 to the driver INSIDE the new root. The book's own
# interactive `chroot` block (04-chroot.sh) is replaced by this scripted
# crossing — same env -i, same PATH, recorded here instead of typed.
set -u
export LFS=/mnt/lfs
# The arch selects the arch-bound overrides (kernel, bootloader, fstab) and
# the serial console; it crosses into the chroot with every other setting.
case "${TUP_ARCH:-$(uname -m)}" in
  aarch64|arm64) export TUP_ARCH=arm64 ;;
  x86_64|amd64)  export TUP_ARCH=x86_64 ;;
  *) echo "$0: unknown arch ${TUP_ARCH:-$(uname -m)}"; exit 1 ;;
esac
LOG=$LFS/sources/log
echo "chain7: waiting for chapter 6"
until grep -q "CHAIN56 COMPLETE" $LOG/chain56.console 2>/dev/null; do sleep 60; done

echo "chain7: root-side pages (ownership, kernel filesystems)"
run_page() {
  ( set -e; cd $LFS/sources; bash -e "$1" ) > "$LOG/ch07-$(basename $1 .sh).log" 2>&1 \
    || { echo "chain7 FAILED on $1"; tail -10 "$LOG/ch07-$(basename $1 .sh).log"; exit 1; }
}
run_page /home/lfs/book/ch07/02-changingowner.sh
run_page /home/lfs/book/ch07/03-kernfs.sh

echo "chain7: staging build system inside \$LFS"
rm -rf $LFS/tup-build
mkdir -p $LFS/tup-build/book/ch07-inner
cp -r /home/lfs/book/ch07 /home/lfs/book/ch08 /home/lfs/book/ch09 /home/lfs/book/ch10 $LFS/tup-build/book/
cp -r /home/lfs/overrides $LFS/tup-build/
cp /home/lfs/driver.sh $LFS/tup-build/
cp $LFS/tup-build/book/ch07/0[5-9]-*.sh $LFS/tup-build/book/ch07/1[0-2]-*.sh $LFS/tup-build/book/ch07-inner/
(cd $LFS/tup-build/book/ch07-inner && ls *.sh | sort > ORDER)
# inside chroot LFS must be EMPTY AND USED: hard-set it in the staged driver
# (${LFS:-...} would treat empty as unset — the colon form's trap).
sed -i 's|^LFS=.*|LFS=${LFS-/mnt/lfs}|' $LFS/tup-build/driver.sh

echo "chain7: crossing into chroot"
chroot "$LFS" /usr/bin/env -i \
  HOME=/root TERM="${TERM:-xterm}" \
  PATH=/usr/bin:/usr/sbin \
  MAKEFLAGS=-j$(nproc) \
  LFS= TUP_ARCH="$TUP_ARCH" TUP_OVERRIDES=/tup-build/overrides \
  /bin/bash /tup-build/driver.sh /tup-build/book/ch07-inner \
  && echo "CHAIN7 COMPLETE" || echo "CHAIN7 FAILED IN CHROOT"
