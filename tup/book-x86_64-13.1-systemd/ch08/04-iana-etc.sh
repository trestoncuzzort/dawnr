#!/bin/bash
# 8.4. Iana-Etc-20260805
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/iana-etc.html
# TUP_TARBALL=iana-etc-20260805.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/04-iana-etc.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_c19910171501b50cbddd6328602d9fa3616cce57366f161eb6f46f1317b9df73'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cp -v services protocols /etc
# TUP_BLOCK_END=001
TUP_UNSELECTED_c19910171501b50cbddd6328602d9fa3616cce57366f161eb6f46f1317b9df73
