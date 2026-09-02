#!/bin/bash
# OVERRIDE ch07/createfiles. Two edits to the book's own bytes, both named:
#   1. `exec /usr/bin/bash --login` exists so a HUMAN re-enters the shell once
#      /etc/passwd is real; under the driver it would replace the page's shell
#      mid-page and silently skip every later block, so it becomes a no-op.
#   2. `ln -sv` -> `ln -sfv` for /etc/mtab, so a re-run after a failed page is
#      idempotent. Everything else on the page already is (the passwd/group
#      heredocs truncate before the tester lines append).
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the createfiles page"; exit 1; }
sed -e 's|^exec /usr/bin/bash --login$|: # exec-to-login skipped under the driver|' \
    -e 's|^ln -sv /proc/self/mounts /etc/mtab$|ln -sfv /proc/self/mounts /etc/mtab|' \
    "$PAGE" | bash -e
