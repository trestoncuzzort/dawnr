#!/bin/bash
# 9.4. Managing Devices
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/symlinks.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch09/04-symlinks.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_6ccd80ed751720a066f5691eb79b636f5d31ca337efd333b30d8b8ffc5fb5f73'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
udevadm info -a -p /sys/class/video4linux/video0
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
cat > /etc/udev/rules.d/83-duplicate_devs.rules << "EOF"

# Persistent symlinks for webcam and tuner
KERNEL=="video*", ATTRS{idProduct}=="1910", ATTRS{idVendor}=="0d81", SYMLINK+="webcam"
KERNEL=="video*", ATTRS{device}=="0x036f",  ATTRS{vendor}=="0x109e", SYMLINK+="tvtuner"

EOF
# TUP_BLOCK_END=002
TUP_UNSELECTED_6ccd80ed751720a066f5691eb79b636f5d31ca337efd333b30d8b8ffc5fb5f73
