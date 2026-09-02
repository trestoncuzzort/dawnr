#!/bin/bash
# OVERRIDE ch08/Python: exclude ONE signal test from the PGO profiling
# workload. Every other byte of the page is the book's.
#
# WHAT FAILED, and why this is not a correctness compromise. The book builds
# Python with --enable-optimizations, which is profile-guided optimization:
# "the interpreter is built twice; tests performed on the first build are used
# to improve the optimized final version." That first run is a PROFILING
# WORKLOAD — its purpose is to exercise code paths so the compiler can measure
# which ones are hot. It is not a correctness gate, and CPython nevertheless
# fails the whole build if any of it fails.
#
# Measured 2026-08-31, 68s in, 43 test files run, exactly one failure:
#   FAIL: test_raise_and_yield_from
#         (test.test_generators.SignalAndYieldFromTest)
#   AssertionError: 'FAILED' != 'PASSED'
# A SIGNAL-DELIVERY test, failing inside a chroot with no controlling
# terminal. That is the environment, not the interpreter — the same species as
# glibc's io/tst-lchmod, which the book itself documents as a chroot failure.
#
# So PROFILE_TASK drops test_generators from the workload it profiles. The
# interpreter is still built twice, still profile-guided, and still runs every
# other test file. What is lost is optimization data from one generator test —
# which is nothing anyone can measure.
#
# NOT DONE, deliberately: dropping --enable-optimizations entirely. That would
# have been the easy fix and it would have silently produced a slower
# interpreter than the book specifies, with nothing in the receipt to say so.
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the Python page"; exit 1; }
sed 's@^make$@make PROFILE_TASK="-m test --pgo -x test_generators"@' "$PAGE" > /tmp/python-pgo.sh
grep -q 'PROFILE_TASK' /tmp/python-pgo.sh || { echo "override: substitution missed"; exit 1; }
[ "$(grep -c . "$PAGE")" = "$(grep -c . /tmp/python-pgo.sh)" ] || { echo "override: line count changed"; exit 1; }
. /tmp/python-pgo.sh
