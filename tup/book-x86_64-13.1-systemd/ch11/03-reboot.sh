#!/bin/bash
# 11.3. Rebooting the System
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter11/reboot.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch11/03-reboot.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_552288ff763e0d4050e0c613c2ae285664ef6dfaf4bec0e7b503459974a5dad8'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
logout
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
umount -v $LFS/dev/pts
mountpoint -q $LFS/dev/shm && umount -v $LFS/dev/shm
umount -v $LFS/dev
umount -v $LFS/run
umount -v $LFS/proc
umount -v $LFS/sys
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
umount -v $LFS/home
umount -v $LFS
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
umount -v $LFS
# TUP_BLOCK_END=004
TUP_UNSELECTED_552288ff763e0d4050e0c613c2ae285664ef6dfaf4bec0e7b503459974a5dad8
