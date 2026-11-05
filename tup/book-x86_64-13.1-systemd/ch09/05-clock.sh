#!/bin/bash
# 9.5. Configuring the System Clock
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/clock.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch09/05-clock.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_e2ffd8d05d865c6079c702912b363134366be2dae58fe92ab8b8e9fd5cc29387'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cat > /etc/adjtime << "EOF"
0.0 0 0.0
0
LOCAL
EOF
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
timedatectl set-local-rtc 1
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
timedatectl set-time YYYY-MM-DD HH:MM:SS
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
timedatectl set-timezone TIMEZONE
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
timedatectl list-timezones
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
systemctl disable systemd-timesyncd
# TUP_BLOCK_END=006
TUP_UNSELECTED_e2ffd8d05d865c6079c702912b363134366be2dae58fe92ab8b8e9fd5cc29387
