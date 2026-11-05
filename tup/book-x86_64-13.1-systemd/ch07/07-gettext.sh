#!/bin/bash
# 7.7. Gettext-1.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/gettext.html
# TUP_TARBALL=gettext-1.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/07-gettext.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_58383a3b3bb3ff562951893cb121c76e6457a079e5eda95d7feb58dc77311032'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --disable-shared
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
cp -v gettext-tools/src/{msgfmt,msgmerge,xgettext} /usr/bin
# TUP_BLOCK_END=003
TUP_UNSELECTED_58383a3b3bb3ff562951893cb121c76e6457a079e5eda95d7feb58dc77311032
