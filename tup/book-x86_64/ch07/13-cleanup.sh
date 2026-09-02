# 7.13. Cleaning up and Saving the Temporary System
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/cleanup.html
# TUP_ACTION_PAGE

rm -rf /usr/share/{info,man,doc}/*

find /usr/{lib,libexec} -name \*.la -delete

rm -rf /tools

exit

mountpoint -q $LFS/dev/shm && umount $LFS/dev/shm
umount $LFS/dev/pts
umount $LFS/{sys,proc,run,dev}

cd $LFS
tar -cJpf $HOME/lfs-temp-tools-12.4.tar.xz .
