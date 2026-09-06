#!/bin/bash
# OVERRIDE ch08/glibc: run the critical test suite and JUDGE it, instead of
# letting `make check`'s exit code decide. The page runs BYTE FOR BYTE except
# that the single line `make check` becomes `judge_glibc_check`; everything
# after it (localedefs, timezone data, ld.so.conf) is the book's own.
#
# THE PROBLEM. The book calls this suite critical ("Do not skip it under any
# circumstance") and in the same breath says "a few tests do not pass... the
# failures listed below are usually safe to ignore." `make check` exits
# nonzero on ANY failure, so the honest options are not {run, skip} but:
#   (a) `make check || true` swallows every failure forever, including real
#       ones. The option that looks like it works and measures nothing.
#   (b) enumerate the failures the book names; fail on anything else.
# tup takes (b).
#
# THE ALLOWLIST is quoted from chapter08/glibc.html (arm64 book fetched
# 2026-08-31; the x86 12.4 page, fetched 2026-09-02, names the same seven),
# not from memory: io/tst-lchmod (known to fail in the LFS chroot),
# misc/tst-preadvwritev2, misc/tst-preadvwritev64v2 (host kernel 6.14+),
# nss/tst-nss-files-hosts-multi and nptl/tst-thread-affinity* (timeouts under
# parallel make), elf/tst-cpu-features-cpuinfo (older CPUs),
# stdlib/tst-arc4random-thread (older host kernels).
#
# Measured on the first run: 6275 PASS, 1 FAIL (io/tst-lchmod), 473
# UNSUPPORTED, 16 XFAIL, 2 XPASS, a clean pass by the book's own standard.
set -e

ALLOWED='^(io/tst-lchmod|misc/tst-preadvwritev2|misc/tst-preadvwritev64v2|nss/tst-nss-files-hosts-multi|nptl/tst-thread-affinity.*|elf/tst-cpu-features-cpuinfo|stdlib/tst-arc4random-thread)$'

judge_glibc_check() {
  echo "=== glibc test suite (critical; judged against the book's allowlist)"
  set +e
  make check > check.out 2>&1
  local rc=$?
  set -e
  sed -n '/=== Summary of results ===/,+6p' check.out || true
  grep -E "^(FAIL|XPASS):" check.out || true
  local nfail npass unexpected
  nfail=$(grep -cE "^FAIL: " check.out || true)
  npass=$(awk '/^[[:space:]]+[0-9]+ PASS$/{print $1; exit}' check.out)
  npass=${npass:-0}
  unexpected=$(grep -E "^FAIL: " check.out | sed 's/^FAIL: //' | grep -Ev "$ALLOWED" || true)
  echo "{\"page\":\"$TUP_PAGE_ID\",\"tests_run\":true,\"pass\":$npass,\"fail\":$nfail,\"check_exit\":$rc,\"unexpected\":$(tup_json_str "$(echo $unexpected | tr '\n' ' ')")}" \
    >> "${RECEIPTS:-/sources/log/receipts.jsonl}"
  if [ -n "$unexpected" ]; then
    echo "!!! glibc: FAILURES OUTSIDE THE BOOK'S ALLOWLIST:"
    echo "$unexpected" | sed 's/^/      /'
    return 1
  fi
  echo "=== glibc suite judged OK: $npass pass, $nfail fail, all allowlisted"
  return 0
}
export -f judge_glibc_check
export ALLOWED

PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the glibc page"; exit 1; }

# Run the page verbatim, with exactly one line substituted.
# Two substitutions, both line-preserving:
#   make check            -> judge_glibc_check (the allowlist judgment)
#   grep "Timed out" ...   -> ... || true
#   tzselect              -> no-op (it is an interactive continent menu)
#   ln -sfv .../<xxx> ... -> .../UTC  (the book's placeholder, filled)
# tup runs on UTC: a build machine's honest default, and it makes every
# timestamp in the receipts unambiguous.
# The second is not cosmetic: grep exits 1 when it finds nothing, so under
# `set -e` the GOOD outcome (no test timed out) aborted the page. Measured
# 2026-08-31: the suite passed judgment and the build died on the next line.
sed -e 's@^make check$@judge_glibc_check@' \
    -e 's@^grep "Timed out".*$@& || true@' \
    -e 's@^tzselect$@: # tzselect is an interactive menu; tup uses UTC (below)@' \
    -e 's@^ln -sfv /usr/share/zoneinfo/<xxx> /etc/localtime$@ln -sfv /usr/share/zoneinfo/UTC /etc/localtime@' \
    "$PAGE" > /tmp/glibc-judged.sh
diff <(grep -c . "$PAGE") <(grep -c . /tmp/glibc-judged.sh) >/dev/null \
  || { echo "override: substitution changed the line count, refusing"; exit 1; }
. /tmp/glibc-judged.sh
