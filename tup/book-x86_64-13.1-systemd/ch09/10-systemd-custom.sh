#!/bin/bash
# 9.10. Systemd Usage and Configuration
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/systemd-custom.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch09/10-systemd-custom.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_c7696aa20a3b9b3111fcf4d7bd050c6d43c4300cb885da3b3afea09d658d1613'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -pv /etc/systemd/system/getty@tty1.service.d

cat > /etc/systemd/system/getty@tty1.service.d/noclear.conf << EOF
[Service]
TTYVTDisallocate=no
EOF
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
systemctl mask tmp.mount
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
mkdir -p /etc/tmpfiles.d
cp /usr/lib/tmpfiles.d/tmp.conf /etc/tmpfiles.d
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
mkdir -pv /etc/systemd/system/foobar.service.d

cat > /etc/systemd/system/foobar.service.d/foobar.conf << EOF
[Service]
Restart=always
RestartSec=30
EOF
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
mkdir -pv /etc/systemd/coredump.conf.d

cat > /etc/systemd/coredump.conf.d/maxuse.conf << EOF
[Coredump]
MaxUse=5G
EOF
# TUP_BLOCK_END=005
TUP_UNSELECTED_c7696aa20a3b9b3111fcf4d7bd050c6d43c4300cb885da3b3afea09d658d1613
