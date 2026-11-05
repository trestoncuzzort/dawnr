#!/bin/bash
# 7.4. Entering the Chroot Environment
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/chroot.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch07/04-chroot.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_1aa839c20259e288062f5b7f9d4cc6e40bb363e6baffa131523e702c6996b29c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
chroot "$LFS" /usr/bin/env -i   \
    HOME=/root                  \
    TERM="$TERM"                \
    PS1='(lfs chroot) \u:\w\$ ' \
    PATH=/usr/bin:/usr/sbin     \
    MAKEFLAGS="-j$(nproc)"      \
    TESTSUITEFLAGS="-j$(nproc)" \
    /bin/bash --login
# TUP_BLOCK_END=001
TUP_UNSELECTED_1aa839c20259e288062f5b7f9d4cc6e40bb363e6baffa131523e702c6996b29c
