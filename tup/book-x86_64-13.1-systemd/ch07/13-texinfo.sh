#!/bin/bash
# 7.13. Texinfo-7.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/texinfo.html
# TUP_TARBALL=texinfo-7.3.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/13-texinfo.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_74aee20bd1e6391b1f13a62af1ae88380cb7ceb9327aeac920e80c92b83d43b3'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_74aee20bd1e6391b1f13a62af1ae88380cb7ceb9327aeac920e80c92b83d43b3
