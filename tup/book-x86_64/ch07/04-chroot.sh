# 7.4. Entering the Chroot Environment
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter07/chroot.html
# TUP_ACTION_PAGE

chroot "$LFS" /usr/bin/env -i   \
    HOME=/root                  \
    TERM="$TERM"                \
    PS1='(lfs chroot) \u:\w\$ ' \
    PATH=/usr/bin:/usr/sbin     \
    MAKEFLAGS="-j$(nproc)"      \
    TESTSUITEFLAGS="-j$(nproc)" \
    /bin/bash --login
