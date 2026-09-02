#!/bin/bash
# OVERRIDE ch08/shadow: `passwd root` prompts a terminal. Initial root
# password is set non-interactively to "tup" — CHANGE IT AT FIRST BOOT; the
# receipt records that this override exists precisely so nobody pretends the
# password was chosen well.
set -e
PAGE="$TUP_PAGE"
sed 's|^passwd root$|echo root:tup \| chpasswd   # initial password, change at first boot|' "$PAGE" | bash -e
