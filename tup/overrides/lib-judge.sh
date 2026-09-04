# lib-judge.sh — shared judgment for DejaGnu-style suites. Sourced by
# overrides; not a page override itself.
#
# The problem these solve: `make check` and `make -k check` exit nonzero for
# reasons that are not test failures (an unresolved testcase, a subdirectory
# that cannot build its harness), so the exit code is not the verdict. Each
# suite is judged by the criterion its own book page states — and where the
# book states NO mechanical criterion, that fact is recorded rather than a
# threshold being invented.

# Zero-FAIL judgment, for suites whose book page gives that recipe verbatim
# ("For a list of failed tests, run: grep '^FAIL:' $(find -name '*.log')").
judge_zero_fail() {
  local name="$1"; shift
  local rc=0
  "$@" > check.out 2>&1 || rc=$?
  local fails
  fails=$(grep -h "^FAIL:" $(find . -name "*.log" 2>/dev/null) 2>/dev/null | sort -u)
  local nfail; nfail=$(printf '%s' "$fails" | grep -c . || true)
  local unres; unres=$(grep -hoE "# of unresolved testcases[[:space:]]+[0-9]+" check.out \
                       | grep -oE "[0-9]+$" | awk '{s+=$1} END{print s+0}')
  local pass;  pass=$(grep -hoE "# of expected passes[[:space:]]+[0-9]+" check.out \
                       | grep -oE "[0-9]+$" | awk '{s+=$1} END{print s+0}')
  echo "{\"page\":$(tup_json_str "$name"),\"tests_run\":true,\"criterion\":\"zero FAIL: lines (the book's own recipe)\",\"expected_passes\":$pass,\"fail_lines\":$nfail,\"unresolved\":$unres,\"make_exit\":$rc}" \
    >> "${RECEIPTS:-/sources/log/receipts.jsonl}"
  echo "=== $name: $pass expected passes, $nfail FAIL lines, $unres unresolved (make exit $rc)"
  if [ "$nfail" -gt 0 ]; then
    echo "!!! $name: the book's criterion is zero failures; these failed:"
    printf '%s\n' "$fails" | sed 's/^/      /'
    return 1
  fi
  echo "=== $name: judged OK by the book's own criterion"
  return 0
}

# Record-and-continue, for suites whose book page declines to give a pass
# criterion. Used ONLY where the book itself says a mechanical rule is not
# available; the numbers and the full failure list go into the receipt so a
# reader can judge what the book would not.
judge_record_only() {
  local name="$1"; shift
  local rc=0
  "$@" > check.out 2>&1 || rc=$?
  local fails nfail pass unexp
  fails=$(grep -h "^FAIL:" $(find . -name "*.log" 2>/dev/null) 2>/dev/null | sort -u)
  nfail=$(printf '%s' "$fails" | grep -c . || true)
  pass=$(grep -hoE "# of expected passes[[:space:]]+[0-9]+" check.out \
          | grep -oE "[0-9]+$" | awk '{s+=$1} END{print s+0}')
  unexp=$(grep -hoE "# of unexpected failures[[:space:]]+[0-9]+" check.out \
          | grep -oE "[0-9]+$" | awk '{s+=$1} END{print s+0}')
  printf '%s\n' "$fails" > "${LOGDIR:-/sources/log}/$name-FAIL-list.txt"
  echo "{\"page\":$(tup_json_str "$name"),\"tests_run\":true,\"criterion\":\"RECORDED, NOT JUDGED — the book states no mechanical pass criterion\",\"expected_passes\":$pass,\"unexpected_failures\":$unexp,\"fail_lines\":$nfail,\"make_exit\":$rc,\"fail_list\":$(tup_json_str "$name-FAIL-list.txt")}" \
    >> "${RECEIPTS:-/sources/log/receipts.jsonl}"
  echo "=== $name: $pass expected passes, $unexp unexpected failures, $nfail FAIL lines"
  echo "=== $name: RECORDED, NOT JUDGED — the book gives no pass criterion here;"
  echo "    the full failure list is banked at $name-FAIL-list.txt for a human."
  return 0
}
