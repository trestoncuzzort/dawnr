#!/bin/bash
# 8.2. Package Management
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/pkgmgt.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch08/02-pkgmgt.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_b2abe59ca6c46887c158dfa6381fd3d34182ae68b262562ee8e5de0895f0e84a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
grep -l 'libfoo.*deleted' /proc/*/maps | tr -cd 0-9\\n | xargs -r ps u
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr/pkg/libfoo/1.1
make
make install
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
./configure --prefix=/usr
make
make DESTDIR=/usr/pkg/libfoo/1.1 install
# TUP_BLOCK_END=003
TUP_UNSELECTED_b2abe59ca6c46887c158dfa6381fd3d34182ae68b262562ee8e5de0895f0e84a
