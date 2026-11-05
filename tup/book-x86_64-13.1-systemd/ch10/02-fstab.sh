#!/bin/bash
# 10.2. Creating the /etc/fstab File
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/fstab.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch10/02-fstab.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_5b89121d3b583e801464d4bc5052405499c66ad15f8406d9452d6c83f4b15614'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cat > /etc/fstab << "EOF"
# Begin /etc/fstab

# file system  mount-point  type     options             dump  fsck
#                                                              order

/dev/<xxx>     /            <fff>    defaults            1     1
/dev/<yyy>     swap         swap     pri=1               0     0

# End /etc/fstab
EOF
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
cat >> /etc/fstab << "EOF"
/dev/<zzz>  /boot/efi  vfat  rw,relatime,codepage=437,iocharset=iso8859-1   0   2
EOF
# TUP_BLOCK_END=002
TUP_UNSELECTED_5b89121d3b583e801464d4bc5052405499c66ad15f8406d9452d6c83f4b15614
