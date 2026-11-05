# Sourced by the reviewed native13 recipes. Bash and temporary coreutils only.
# A failed required suite stops the build for review. The only accepted
# non-pass results are complete result lines listed in a reviewed
# suite-exceptions/<package>.allow file for exactly this package version;
# see suite-exceptions/README.md for what such a review must contain.
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/glibc.html
native_reviewed_exceptions() {
  local package=$1 directory=$2 allow floor status=0
  # Only harnesses that name every non-pass result on its own line.
  case "$package" in glibc|gcc|binutils) ;; *) return 98 ;; esac
  allow=$(dirname -- "${BASH_SOURCE[0]}")/suite-exceptions/$package.allow
  [ -f "$allow" ] && [ ! -L "$allow" ] || return 98
  grep -E '^(FAIL|XPASS|UNRESOLVED|ERROR): ' "$directory/summary.results" > "$directory/nonpass.unsorted" || status=$?
  [ "$status" -le 1 ] || return 125
  # glibc repeats each result in its aggregate and per-directory summaries.
  LC_ALL=C sort -u "$directory/nonpass.unsorted" > "$directory/nonpass.observed" || return 125
  rm -- "$directory/nonpass.unsorted" || return 125
  # A failure count without named results cannot be reviewed line by line.
  [ -s "$directory/nonpass.observed" ] || return 98
  status=0
  grep -v -E '^(#|@|[[:space:]]*$)' "$allow" > "$directory/nonpass.reviewed" || status=$?
  [ "$status" -le 1 ] || return 125
  status=0
  LC_ALL=C grep -F -x -v -f "$directory/nonpass.reviewed" "$directory/nonpass.observed" > "$directory/nonpass.unexplained" || status=$?
  [ "$status" -le 1 ] || return 125
  [ ! -s "$directory/nonpass.unexplained" ] || return 98
  # DejaGnu totals must be fully accounted for by the named lines just reviewed.
  awk '/^FAIL: / { fail++ } /^XPASS: / { xpass++ } /^UNRESOLVED: / { unresolved++ }
       /^# of unexpected failures[[:space:]]/ { cfail += $NF; counted = 1 }
       /^# of unexpected successes[[:space:]]/ { cxpass += $NF; counted = 1 }
       /^# of unresolved testcases[[:space:]]/ { cunresolved += $NF; counted = 1 }
       END { exit (counted && (fail != cfail || xpass != cxpass || unresolved != cunresolved)) }' \
    "$directory/summary.results" || return 98
  # Positive coverage: an exception never excuses a suite that mostly did not run.
  floor=$(sed -n 's/^@min-pass[[:space:]]\{1,\}\([1-9][0-9]*\)$/\1/p' "$allow") || return 125
  [[ $floor =~ ^[1-9][0-9]*$ ]] || return 98
  awk -v floor="$floor" '/^PASS: / { if (!seen[$0]++) lines++ } /^# of expected passes[[:space:]]/ { counted += $NF }
       END { exit !((counted > 0 ? counted : lines) >= floor) }' "$directory/summary.results" || return 98
  sha256sum -- "$allow" > "$directory/nonpass.exceptions.sha256" || return 125
}

native_judge_suite() {
  local package=$1 directory=$2 file summary result rc=0
  local -a summary_names=()
  case "$package" in
    gcc) summary_names=(gcc.sum g++.sum libstdc++.sum) ;;
    binutils) summary_names=(binutils.sum gas.sum ld.sum) ;;
    glibc) [ -s "$directory/results/tests.sum" ] || return 98 ;;
    gmp|mpfr|coreutils-root|coreutils-user) ;;
    Python)
      [ -s "$directory/results/native-python.xml" ] && [ -s "$directory/results/native-python-full.trs" ] || return 98
      [ "$(grep -c '^:test-result: PASS$' "$directory/results/native-python-backports.trs")" = 2 ] || return 98 ;;
    python-temporary)
      [ "$(grep -c '^:test-result: PASS$' "$directory/results/native-python-backports.trs")" = 2 ] || return 98 ;;
    bzip2)
      [ "$(grep -c '^:test-result: PASS$' "$directory/results/native-bzip2.trs")" = 3 ] || return 98 ;;
    sqlite)
      [ "$(grep -c '^:test-result: PASS$' "$directory/results/native-sqlite.trs")" = 9 ] || return 98 ;;
    expect|tcl)
      # Tcl's harness can exit zero after reporting failures. Require a single
      # aggregate result with real passes and no failures; preserve skip counts.
      awk '/^[^[:space:]]+:[[:space:]]+Total[[:space:]]+[0-9]+.*Passed[[:space:]]+[0-9]+.*Skipped[[:space:]]+[0-9]+.*Failed[[:space:]]+[0-9]+/ {
        if ($1=="all.tcl:") aggregate++;
        for (i=1; i<NF; i++) { if ($i=="Total") total+=$(i+1); if ($i=="Passed") passed+=$(i+1); if ($i=="Failed") failed+=$(i+1) }
      } /(^====.*FAILED|make.*\*\*\*.*Error)/ { failed++ }
      END { exit !(aggregate>=1 && total>0 && passed>0 && failed==0) }' "$directory/command.console" || return 98
      cp "$directory/command.console" "$directory/summary.results" || return 125
      return 0 ;;
    tar|kbd)
      # These use Autotest, not Automake .trs or DejaGNU .sum.
      [ -s "$directory/results/tests/testsuite.log" ] || return 98
      grep -Eq '^(All )?[1-9][0-9]* tests? (were successful|was successful|behaved as expected)[.]$' "$directory/results/tests/testsuite.log" || return 98
      grep -Eq '^[[:space:]]*[0-9]+:.*[[:space:]]ok[[:space:]]*$' "$directory/command.console" || return 98
      if [ "$package" = kbd ]; then
        [ "$(grep -c '^:test-result: PASS$' "$directory/results/native-kbd-keymaps.trs")" = 18 ] || return 98
      fi
      cp "$directory/results/tests/testsuite.log" "$directory/summary.results" || return 125
      return 0 ;;
    *) return 96 ;;
  esac
  # Judge machine-readable results only. Compiler/configure logs can contain
  # deliberate error text from negative tests; retain them, but don't confuse
  # that text with a test-harness verdict.
  case "$package" in
    gmp|mpfr|coreutils-root|coreutils-user|Python|python-temporary|bzip2|sqlite) find "$directory/results" -type f -name '*.trs' -print0 ;;
    *) find "$directory/results" -type f -name '*.sum' -print0 ;;
  esac > "$directory/summary-files.list" || return 125
  [ -s "$directory/summary-files.list" ] || return 98
  : > "$directory/summary.results"
  while IFS= read -r -d '' file; do
    cat -- "$file" >> "$directory/summary.results" || return 125
  done < "$directory/summary-files.list"
  # This temporary list contains absolute builder paths; the relative paths in
  # files.sha256 are the portable record kept with the results instead.
  rm -- "$directory/summary-files.list" || return 125
  grep -Eq '^(PASS:|:test-result: PASS|# of expected passes[[:space:]]+[1-9])' "$directory/summary.results" || return 98
  grep -Eq '^(FAIL:|XPASS:|UNRESOLVED:|ERROR:|:test-result: (FAIL|XPASS|ERROR)|# of (unexpected failures|unexpected successes|unresolved testcases)[[:space:]]+[1-9])' "$directory/summary.results" || rc=$?
  case "$rc" in
    1) ;;  # No non-pass result at all.
    0) native_reviewed_exceptions "$package" "$directory" || return 98 ;;
    *) return 98 ;;
  esac
  for summary in "${summary_names[@]}"; do
    result=$(find "$directory/results" -name "$summary" -type f -print) || return 125
    # Exactly one result for each required compiler/linker component.
    [[ -n "$result" && "$result" != *$'\n'* ]] || return 98
    grep -Eq '^# of expected passes[[:space:]]+[1-9]' "$result" || return 98
  done
}

native_required_suite() {
  local package=$1; shift
  local relative directory rc=0 found=0 file result summary missing=0
  case "$package" in glibc|gcc|binutils|gmp|mpfr|expect|coreutils-root|coreutils-user|Python|python-temporary|tar|kbd|bzip2|tcl|sqlite) ;; *) return 96 ;; esac
  [[ "${TUP_TEST_JOBS:-}" =~ ^[1-4]$ ]] || return 96
  [[ "${TUP_PAGE_ID:-}" =~ ^(ch07-inner|ch08)/[0-9][0-9]-[A-Za-z0-9-]+$ && "$native_block" =~ ^[0-9]{3}$ ]] || return 96
  [ "${TUP_NATIVE_CHROOT:-}" = 1 ] && [ "${LFS-}" = "" ] || return 96
  relative=native-suites/${TUP_PAGE_ID/\//-}-$native_block
  directory=/sources/log/$relative
  [ ! -L /sources ] && [ ! -L /sources/log ] || return 96
  if [ ! -e /sources/log/native-suites ]; then mkdir /sources/log/native-suites || return 96; fi
  [ ! -L /sources/log/native-suites ] || return 96
  mkdir "$directory" || return 96
  # A new Bash for compound suite commands preserves errexit even when this
  # function is used as a condition. Capture the actual suite status separately.
  "$@" > "$directory/command.console" 2>&1 || rc=$?
  cat "$directory/command.console" || return 125
  printf '%s\n' "$rc" > "$directory/command.exit"
  mkdir "$directory/results" || return 125
  # Keep all suite output before driver.sh removes the successful package tree.
  # Do not follow source-tree symlinks or accept special files as evidence.
  find . -type f \( -name '*.log' -o -name '*.sum' -o -name '*.out' -o -name '*.test-result' -o -name '*.trs' -o -name 'native-python.xml' -o -name 'native-keymap-*.bin' \) -print0 > "$directory/capture-files.list" || return 125
  while IFS= read -r -d '' file; do
    case "$file" in *$'\n'*|*\\*) echo 'unsupported evidence filename' >&2; return 125 ;; esac
    cp --parents -- "$file" "$directory/results" || return 125
    found=$((found + 1))
  done < "$directory/capture-files.list"
  rm -- "$directory/capture-files.list" || return 125
  # Expect's authoritative Tcl summary is emitted to the retained console.
  [ "$found" -gt 0 ] || [[ "$package" = expect || "$package" = tcl ]] || missing=1
  # Exact current-version result formats. A zero make status without positive
  # evidence, or with FAIL/XPASS/UNRESOLVED, cannot be a passing receipt.
  native_judge_suite "$package" "$directory" || missing=1
  local command_rc=$rc reviewed=0 exceptions=null
  if [ "$missing" = 0 ] && [ -s "$directory/nonpass.observed" ]; then
    # The judge accepted every named non-pass result as a reviewed exception.
    # Only then is a non-zero status of the suite command itself explained.
    reviewed=$(wc -l < "$directory/nonpass.observed") || return 125
    exceptions=$(cut -d' ' -f1 "$directory/nonpass.exceptions.sha256") || return 125
    exceptions=$(tup_json_str "$exceptions")
    rc=0
  fi
  [ "$missing" = 0 ] || { echo 'required suite result evidence is missing or reports failures' >&2; [ "$rc" != 0 ] || rc=98; }
  [ "$missing" != 0 ] || [ "$rc" = 0 ] || echo 'required suite command failed without a reviewed, named result' >&2
  printf '%s\n' "$rc" > "$directory/verdict.exit"
  (
    cd "$directory" || exit 1
    find . -type f ! -name files.sha256 -printf '%P\0' | LC_ALL=C sort -z |
      while IFS= read -r -d '' file; do sha256sum -- "$file" || exit 1; done > files.sha256
    sync -f .
  ) || return 125
  result=$(sha256sum "$directory/files.sha256") || return 125
  local status=failed coverage=upstream-suite
  case "$package" in
    python-temporary) coverage=focused-backport-regressions ;;
    bzip2) coverage=upstream-embedded-comparisons ;;
    sqlite) coverage=local-built-binary-regressions ;;
  esac
  [ "$rc" != 0 ] || status=passed
  printf '{"native_suite_evidence":{"package":%s,"status":%s,"exit_code":%s,"directory":%s,"manifest_sha256":%s,"coverage":%s,"command_exit_code":%s,"reviewed_exceptions":%s,"exceptions_sha256":%s}}\n' \
    "$(tup_json_str "$package")" "$(tup_json_str "$status")" "$rc" \
    "$(tup_json_str "$relative")" "$(tup_json_str "${result%% *}")" "$(tup_json_str "$coverage")" \
    "$command_rc" "$reviewed" "$exceptions" >> "$RECEIPTS" || return 125
  return "$rc"
}
