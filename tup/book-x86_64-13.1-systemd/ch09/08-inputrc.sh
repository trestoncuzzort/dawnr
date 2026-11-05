#!/bin/bash
# 9.8. Creating the /etc/inputrc File
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/inputrc.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch09/08-inputrc.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a09ade1a0477132717e05df1dff3b6f4303dcd0ac6a8f00e2d4d83078d6b83e7'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cat > /etc/inputrc << "EOF"
# Begin /etc/inputrc
# Modified by Chris Lynn <roryo@roryo.dynup.net>

# Allow the command prompt to wrap to the next line
set horizontal-scroll-mode Off

# Enable 8-bit input
set meta-flag On
set input-meta On

# Turns off 8th bit stripping
set convert-meta Off

# Keep the 8th bit for display
set output-meta On

# none, visible or audible
set bell-style none

# All of the following map the escape sequence of the value
# contained in the 1st argument to the readline specific functions
"\eOd": backward-word
"\eOc": forward-word

# for linux console
"\e[1~": beginning-of-line
"\e[4~": end-of-line
"\e[5~": beginning-of-history
"\e[6~": end-of-history
"\e[3~": delete-char
"\e[2~": quoted-insert

# for xterm
"\eOH": beginning-of-line
"\eOF": end-of-line

# for Konsole
"\e[H": beginning-of-line
"\e[F": end-of-line

# uncomment for history search mode with up/down
# "\e[A": history-search-backward
# "\e[B": history-search-forward

# End /etc/inputrc
EOF
# TUP_BLOCK_END=001
TUP_UNSELECTED_a09ade1a0477132717e05df1dff3b6f4303dcd0ac6a8f00e2d4d83078d6b83e7
