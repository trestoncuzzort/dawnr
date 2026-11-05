#!/bin/bash
# 7.15. Cleaning up and Saving the Temporary System
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/cleanup.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch07/15-cleanup.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_3b0370e6ee2e7845f9be25752b49568d199802862c19012434aaf81f25ec6a4d'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
rm -rf /usr/share/{info,man,doc}/*
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
find /usr/{lib,libexec} -name \*.la -delete
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
rm -rf /tools
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
exit
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
mountpoint -q $LFS/dev/shm && umount $LFS/dev/shm
umount $LFS/dev/pts
umount $LFS/{sys,proc,run,dev}
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
cd $LFS
tar -cJpf $HOME/lfs-temp-tools-13.1-systemd.tar.xz .
# TUP_BLOCK_END=006
TUP_UNSELECTED_3b0370e6ee2e7845f9be25752b49568d199802862c19012434aaf81f25ec6a4d
