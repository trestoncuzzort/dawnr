#!/bin/bash
# 9.9. Creating the /etc/shells File
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/etcshells.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch09/09-etcshells.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_bb2fd16787b8d4000c8f3d2f2429a2ad5cf2e97141515b33c37aeecdea1e9d68'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cat > /etc/shells << "EOF"
# Begin /etc/shells

/bin/sh
/bin/bash

# End /etc/shells
EOF
# TUP_BLOCK_END=001
TUP_UNSELECTED_bb2fd16787b8d4000c8f3d2f2429a2ad5cf2e97141515b33c37aeecdea1e9d68
