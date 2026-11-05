#!/bin/bash
# 8.85. Cleaning Up
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/cleanup.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/85-cleanup.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_bbb67d6083133e49424f4fb7acd06ac110dbb472b727b314107834507a0f7c8a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
rm -rf /tmp/{*,.*}
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
find /usr/lib /usr/libexec -name \*.la -delete
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
find /usr -depth -name $(uname -m)-lfs-linux-gnu\* | xargs rm -rf
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
userdel -r tester
# TUP_BLOCK_END=004
TUP_UNSELECTED_bbb67d6083133e49424f4fb7acd06ac110dbb472b727b314107834507a0f7c8a
