#!/bin/bash
# 7.3. Preparing Virtual Kernel File Systems
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/kernfs.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch07/03-kernfs.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_6cad02a48534bf672f2ecb4cbe618f7b41b74d0264215f58076cea04e1104023'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -pv $LFS/{dev,proc,sys,run}
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mount -v --bind /dev $LFS/dev
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
mount -vt devpts devpts -o gid=5,mode=0620 $LFS/dev/pts
mount -vt proc proc $LFS/proc
mount -vt sysfs sysfs $LFS/sys
mount -vt tmpfs tmpfs $LFS/run
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
if [ -h $LFS/dev/shm ]; then
  install -v -d -m 1777 $LFS$(realpath /dev/shm)
else
  mount -vt tmpfs -o nosuid,nodev tmpfs $LFS/dev/shm
fi
# TUP_BLOCK_END=004
TUP_UNSELECTED_6cad02a48534bf672f2ecb4cbe618f7b41b74d0264215f58076cea04e1104023
