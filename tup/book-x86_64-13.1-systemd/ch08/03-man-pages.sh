#!/bin/bash
# 8.3. Man-pages-6.18
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/man-pages.html
# TUP_TARBALL=man-pages-6.18.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/03-man-pages.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_7fbef051a85b9d0e8a9237e7eea8e6455c2e0286f007517a36a426ceeb9ea3be'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
rm -v man3/crypt*
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make -R GIT=false prefix=/usr install
# TUP_BLOCK_END=002
TUP_UNSELECTED_7fbef051a85b9d0e8a9237e7eea8e6455c2e0286f007517a36a426ceeb9ea3be
