#!/bin/bash
# 11.1. The End
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter11/theend.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch11/01-theend.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_c58ae2eae8e76aeddaf25e5c298eecf678198db2fc8a8dac55aa8e92aa139f1c'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
echo 13.1-systemd > /etc/lfs-release
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
cat > /etc/lsb-release << "EOF"
DISTRIB_ID="Linux From Scratch"
DISTRIB_RELEASE="13.1-systemd"
DISTRIB_CODENAME="<your name here>"
DISTRIB_DESCRIPTION="Linux From Scratch"
EOF
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
cat > /etc/os-release << "EOF"
NAME="Linux From Scratch"
VERSION="13.1-systemd"
ID=lfs
PRETTY_NAME="Linux From Scratch 13.1-systemd"
VERSION_CODENAME="<your name here>"
HOME_URL="https://www.linuxfromscratch.org/lfs/"
RELEASE_TYPE="stable"
EOF
# TUP_BLOCK_END=003
TUP_UNSELECTED_c58ae2eae8e76aeddaf25e5c298eecf678198db2fc8a8dac55aa8e92aa139f1c
