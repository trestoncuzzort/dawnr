#!/bin/bash
# OVERRIDE ch08/util-linux: the bare `bash tests/run.sh` is the book's
# POST-REBOOT note, not a build step.
#
# The page runs `bash tests/run.sh --srcdir=$PWD --builddir=$PWD` outside the
# tup_tests_enabled guard, because the guard matches `make ... check|test` and
# this invokes the runner directly. Measured 2026-08-31: it fails immediately
# with "Tests not compiled! Run 'make check-programs' to fix the problem",
# because the suite was never built; the book's own text presents this as
# something to run later, from a booted system, as a normal user.
#
# So it becomes a no-op with the reason recorded, and util-linux's real test
# block (further down, correctly guarded) still obeys the test policy. The
# alternative, running `make check-programs` to satisfy it, would build and
# run a suite the ruling did not ask for, as root, in a chroot.
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: util-linux page missing"; exit 1; }
sed 's@^bash tests/run.sh .*$@: # post-reboot check, not a build step (see override)@' \
  "$PAGE" > /tmp/util-linux-page.sh
grep -q "post-reboot check" /tmp/util-linux-page.sh || { echo "override: sed missed"; exit 1; }
bash -e /tmp/util-linux-page.sh < /dev/null
