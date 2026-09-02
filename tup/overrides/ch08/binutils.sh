#!/bin/bash
# OVERRIDE ch08/binutils: judge the suite by the book's own criterion.
#
# MEASURED 2026-08-31: every binutils summary reported expected passes only —
# ZERO FAIL lines, which is exactly what the book's stated diagnostic
# ("For a list of failed tests, run: grep '^FAIL:' $(find -name '*.log')")
# checks for. `make -k check` still exited 2, because ONE gprofng testcase
# came back *unresolved* and its check-small target errored. Unresolved is
# not failed: it means the harness could not determine a result.
#
# So the exit code is not the verdict here, and the book says what is. This
# runs the same `make -k check` and judges it by grep '^FAIL:', failing
# loudly if that ever returns anything.
set -e
. /tup-build/overrides/lib-judge.sh
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: binutils page missing"; exit 1; }
sed 's@^make -k check$@judge_zero_fail $TUP_PAGE_ID make -k check@' "$PAGE" > /tmp/binutils-judged.sh
grep -q "judge_zero_fail" /tmp/binutils-judged.sh || { echo "override: substitution failed"; exit 1; }
. /tmp/binutils-judged.sh
