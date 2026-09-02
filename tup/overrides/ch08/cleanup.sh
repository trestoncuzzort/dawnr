#!/bin/bash
# OVERRIDE ch08/cleanup: `rm -rf /tmp/{*,.*}` cannot succeed.
#
# The glob expands to include `.` and `..`, and rm REFUSES those and exits 1 —
# always, even when it removed everything else correctly. Under `set -e` the
# final page of chapter 8 therefore fails on its own success, which is the
# same shape as glibc's "no timeouts found" grep and binutils' zero-failure
# exit. A human running the book by hand sees the two refusal lines, shrugs,
# and moves on.
#
# find with -mindepth 1 does exactly what the book means and returns 0.
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cleanup page missing"; exit 1; }
sed 's@^rm -rf /tmp/{\*,\.\*}$@find /tmp -mindepth 1 -maxdepth 1 -exec rm -rf {} +@' \
  "$PAGE" > /tmp/cleanup-page.sh
grep -q "find /tmp -mindepth 1" /tmp/cleanup-page.sh || { echo "override: sed missed"; exit 1; }
bash -e /tmp/cleanup-page.sh < /dev/null
