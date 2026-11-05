#!/bin/bash
# 7.2. Changing Ownership
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/changingowner.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch07/02-changingowner.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_17a0b55ab2a43589c42c368ac59d5212f93fdb115bb87e937ee2b96958a2cc45'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
chown --from lfs -R root:root $LFS/{usr,var,etc,tools}
case $(uname -m) in
  x86_64) chown --from lfs -R root:root $LFS/lib64 ;;
esac
# TUP_BLOCK_END=001
TUP_UNSELECTED_17a0b55ab2a43589c42c368ac59d5212f93fdb115bb87e937ee2b96958a2cc45
