#!/bin/bash
# 8.75. MarkupSafe-3.0.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/markupsafe.html
# TUP_TARBALL=markupsafe-3.0.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/75-markupsafe.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_628c03834bcf8ce57c8709c5f132b7d681258cfe60ed3ae2e941abea276e9091'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist Markupsafe
# TUP_BLOCK_END=002
TUP_UNSELECTED_628c03834bcf8ce57c8709c5f132b7d681258cfe60ed3ae2e941abea276e9091
