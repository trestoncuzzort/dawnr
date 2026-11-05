#!/bin/bash
# 9.6. Configuring the Linux Console
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/console.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch09/06-console.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_89afd0d71de4b08cf4c471c7fc30bc9dfd89e8959dd5ecac42cc6efb9b63a1b0'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
echo FONT=Lat2-Terminus16 > /etc/vconsole.conf
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
cat > /etc/vconsole.conf << "EOF"
KEYMAP=de-latin1
FONT=Lat2-Terminus16
EOF
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
localectl set-keymap MAP
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
localectl set-x11-keymap LAYOUT [MODEL] [VARIANT] [OPTIONS]
# TUP_BLOCK_END=004
TUP_UNSELECTED_89afd0d71de4b08cf4c471c7fc30bc9dfd89e8959dd5ecac42cc6efb9b63a1b0
