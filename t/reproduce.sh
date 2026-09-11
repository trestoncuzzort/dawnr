#!/bin/bash
# t/reproduce.sh -- regenerates every table t/CLAIMS.md's witnesses point to,
# in dependency order, and diffs each regenerated table against the
# committed file it is supposed to match.
#
# House rule for this script: NEVER write over a committed file. Every
# regenerated table is written beside the committed one as <table>.regen.md
# (or, for stages with no committed markdown counterpart, saved with a
# .regen.md name anyway so a reader has something to open) and the diff is
# printed, never applied. Kernel and lifter output goes to private
# directories under t/out/reproduce-* and t/out/lift.repro, never to t/out/
# (which carries 29 tracked lowered-source fixtures a default run would
# silently overwrite) and never to t/out/lift (which a re-lift may have live
# right now -- see --censuses below).
#
# Stages, each behind its own flag so a reader can run one:
#   --tests      test_*.py (house rule: run directly, no pytest) + the
#                surface.py parse/print round trip. No committed table; a
#                stage failure is a test failure, not a table diff.
#   --censuses   coverage_census.py (DafnyBench, then MBPP-DFY alone),
#                nl_census.py, nl_stdin.py, mbpp_gate_order.py, and
#                lift_census.py read against whatever is CURRENTLY in
#                t/out/lift (no re-lift; that is --relift below).
#   --matrix     run_par.py --jobs 16 over t/tasks/ -> AGREEMENT.md.
#   --families   fuzz_lower.py --n 400 --seed 1 --flake 3 --jobs 24, one run
#                over every family (no --tasks/--only filter), rows.json
#                tallied per family and per kernel. No committed table this
#                ties to as a whole corpus run; printed for inspection.
#   --truth      truth_fuzz.py --jobs 24 --seed 1. Same: no single
#                committed table: printed for inspection.
#   --relift     lifter.py --force over the DafnyBench ground_truth corpus
#                into a PRIVATE out/lift.repro (never touches the live
#                out/lift), then lift_census.py and select_lifted.py over
#                that private tree, producing out/lifted-tasks.repro for
#                --sweep.
#   --sweep      run_par.py --jobs 6 over out/lifted-tasks.repro (falling
#                back to the committed out/lifted-tasks with a warning if
#                --relift was not run first) -> COVERAGE-lifted-785.md,
#                then blockers.py --append --replace for the Sole
#                blockers section.
#   --all        every stage above, in the order listed (dependency order:
#                --relift must produce out/lifted-tasks.repro before
#                --sweep can use it).
#
# Every stage prints its own wall clock. The script's exit code is the
# number of regenerated tables that differ from the committed file they
# were diffed against (0 means everything reproduced clean). Stages with
# no committed counterpart (--families, --truth, mbpp_gate_order.py inside
# --censuses) never add to that count; read their printed output by hand.
#
# export PATH before anything that runs a kernel (matrix, families, truth,
# relift, sweep -- lifter.py shells out to dafny too).
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$PATH

set -u
cd /home/tmcuzzort/tup/t || exit 1

DIFF_COUNT=0
CORPUS=/home/tmcuzzort/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth
NL_CENSUS_JSON_DIR=$HOME/t-corpora/nl-census
LIFT_CENSUS_JSON=/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/census.json

stage_start() { echo "=== stage: $1 ==="; STAGE_T0=$(date +%s); }
stage_end() { local t1; t1=$(date +%s); echo "=== stage: $1 done in $((t1 - STAGE_T0))s ==="; }

# regen_diff COMMITTED REGEN DESCRIPTION
# REGEN must already have been written by the caller. Diffs it against
# COMMITTED, prints the diff, and counts a difference toward the script's
# exit code. Missing COMMITTED (nothing to compare against yet) is reported
# but does not count as a difference -- there is nothing stale to flag.
regen_diff() {
  local committed="$1" regen="$2" desc="$3"
  if [ ! -f "$regen" ]; then
    echo "DIFF-SKIP ($desc): $regen was not written, nothing to compare"
    return
  fi
  if [ ! -f "$committed" ]; then
    echo "DIFF-SKIP ($desc): no committed file at $committed to compare against"
    return
  fi
  # Volatile lines are not differences: a table's own timestamp header
  # and a census's run-time line change on every run (2026-09-10, the
  # first full run counted three tables as differing on those alone).
  local volatile='^# t cross-kernel agreement|^Run time:|^- \*\*run time|run time: [0-9.]+s'
  if diff -u <(grep -Ev "$volatile" "$committed") <(grep -Ev "$volatile" "$regen"); then
    echo "MATCH ($desc): $regen == $committed (volatile lines ignored)"
  else
    echo "DIFFERS ($desc): $regen vs $committed (diff above)"
    DIFF_COUNT=$((DIFF_COUNT + 1))
  fi
}

usage() {
  cat <<'EOF'
usage: reproduce.sh [--tests] [--censuses] [--matrix] [--conformance] [--families]
                     [--truth] [--relift] [--sweep] [--all]
Run with no flags to see this message. Pass one or more stage flags to run
just those stages, in the fixed dependency order above (not argv order).
EOF
}

# ---------------------------------------------------------------- --tests
run_tests() {
  stage_start tests
           test_lift_report.py test_lift_rules.py test_mbpp_dfy.py test_cli.py test_lsp.py test_vacuous_requires.py; do
    echo "--- python3 $f ---"
    python3 "$f"
    echo "$f rc=$?"
  done
  echo "--- python3 surface.py --check ---"
  python3 surface.py --check
  echo "surface.py --check rc=$?"
  stage_end tests
}

# ------------------------------------------------------------- --censuses
run_censuses() {
  stage_start censuses
  local tmp
  tmp=$(mktemp -d)
  trap "rm -rf '$tmp'" RETURN

  echo "--- coverage_census.py over DafnyBench (785) ---"
  python3 coverage_census.py "$CORPUS" --name "DafnyBench" \
      --out COVERAGE-dafnybench.regen.md
  regen_diff COVERAGE-dafnybench.md COVERAGE-dafnybench.regen.md "DafnyBench census"

  echo "--- coverage_census.py over MBPP-DFY (164, filtered from the same 785) ---"
  local mbppdir="$tmp/mbpp-dfy-only"
  mkdir -p "$mbppdir"
  find "$CORPUS" -maxdepth 1 -name 'dafny-synthesis_task_id_*.dfy' \
      -exec ln -s {} "$mbppdir/" \;
  echo "filtered corpus: $(ls "$mbppdir" | wc -l) files (expect 164)"
  python3 coverage_census.py "$mbppdir" --name "MBPP-DFY (dafny-synthesis)" \
      --out COVERAGE-mbpp-dfy.regen.md
  regen_diff COVERAGE-mbpp-dfy.md COVERAGE-mbpp-dfy.regen.md "MBPP-DFY census"

  echo "--- nl_census.py (full nl/ corpus, 24748 problems -- this is the slow one) ---"
  python3 nl_census.py --out COVERAGE-nl.regen.md \
      --json "$NL_CENSUS_JSON_DIR/nl-census.regen.json"
  regen_diff COVERAGE-nl.md COVERAGE-nl.regen.md "nl/ census"

  echo "--- nl_stdin.py ---"
  python3 nl_stdin.py --json "$NL_CENSUS_JSON_DIR/nl-stdin.regen.json" \
      --out COVERAGE-nl-stdin.regen.md
  regen_diff COVERAGE-nl-stdin.md COVERAGE-nl-stdin.regen.md "nl/ stdin instrument"

  echo "--- mbpp_gate_order.py (reads out/lift, no re-lift) ---"
  echo "NOTE: no committed markdown for this instrument (out/mbpp-gate-order.md" \
       "is gitignored); its numbers are only quoted into ROADMAP.md prose, so" \
       "there is nothing to diff against automatically -- read the printed" \
       "table by hand against the ROADMAP.md paragraph that cites it."
  python3 mbpp_gate_order.py --markdown out/mbpp-gate-order.regen.md
  cat out/mbpp-gate-order.regen.md

  echo "--- lift_census.py over the CURRENT out/lift (no re-lift here) ---"
  if [ ! -d out/lift ]; then
    echo "WARNING: out/lift does not exist; skipping (run --relift first, or" \
         "populate out/lift the way LIFTER-785.md's own header describes)."
  else
    echo "WARNING: out/lift may be mid-rewrite by another process; a" \
         "concurrent re-lift makes this read unstable. Confirm nothing else" \
         "is writing out/lift before trusting this diff."
    python3 lift_census.py --census-json "$LIFT_CENSUS_JSON" \
        --corpus-dir "$CORPUS" --out out/lift --report out/lift/census_report_785
    cp out/lift/census_report_785.md LIFTER-785.regen.md
    regen_diff LIFTER-785.md LIFTER-785.regen.md "lifter census over current out/lift"
  fi
  stage_end censuses
}

# --------------------------------------------------------------- --matrix
run_matrix() {
  stage_start matrix
  # Private --out so this never touches the 29 tracked lowered-source
  # fixtures under t/out/ (git ls-files t/out confirms they exist).
  python3 run_par.py --jobs 16 --out out/reproduce-matrix \
      --table AGREEMENT.regen.md
  echo "run_par.py rc=$? (exit 1 is normal: it means some cell disagreed)"
  regen_diff AGREEMENT.md AGREEMENT.regen.md "hand-written task matrix"
  stage_end matrix
}

# ----------------------------------------------------------- --conformance
run_conformance() {
  stage_start conformance
  # Private --workdir so this never touches out/reproduce-matrix's or
  # t/out/'s own filenames; conformance.py's own probe/metamorphic task
  # names (fz_p_*, mm_*) never collide with the 34 committed t/tasks/ names.
  python3 conformance.py --jobs 12 --flake 3 \
      --workdir out/reproduce-conformance --out CONFORMANCE.regen.md
  echo "conformance.py rc=$? (exit 1 is normal: it means some cell FAILed)"
  regen_diff CONFORMANCE.md CONFORMANCE.regen.md "conformance suite (13.4)"
  stage_end conformance
}

# ------------------------------------------------------------- --families
run_families() {
  stage_start families
  local out=out/reproduce-families
  rm -rf "$out"
  python3 fuzz_lower.py --out "$out" --n 400 --seed 1 --jobs 24 --flake 3
  echo "fuzz_lower.py rc=$?"
  echo "--- rows.json tallied per family and kernel ---"
  python3 - "$out/rows.json" <<'PYEOF'
import json, sys, re, collections
rows = json.load(open(sys.argv[1]))          # task -> kernel -> [real, twin, agreed, ms]
K = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
def family(name):
    m = re.match(r"fz_(v\d[a-z]+|p|wrong)", name)
    return m.group(1) if m else name
n = collections.Counter(); ok = collections.defaultdict(collections.Counter)
for t, r in rows.items():
    f = family(t); n[f] += 1
    for k in K:
        c = r.get(k)
        if c and c[0] == "verified" and c[1] == "refuted":
            ok[f][k] += 1
print("family     n   " + " ".join(k.ljust(6) for k in K) + "   (verified/refuted per column)")
for f in sorted(n):
    print(f.ljust(10), str(n[f]).ljust(3), " ".join(str(ok[f][k]).ljust(6) for k in K))
print("total".ljust(10), str(sum(n.values())).ljust(3), " ".join(str(sum(ok[f][k] for f in n)).ljust(6) for k in K))
PYEOF
  echo "NOTE: no single committed table covers a full all-families run at" \
       "n=400; the per-wave fuzz-*/rows.json witnesses in the claims batch" \
       "are each a narrower --tasks subset for one new family, not this."
  stage_end families
}

# ---------------------------------------------------------------- --truth
run_truth() {
  stage_start truth
  local out=$HOME/t-truth-fuzz-reproduce
  rm -rf "$out"
  python3 truth_fuzz.py --out "$out" --jobs 24 --seed 1
  echo "truth_fuzz.py rc=$?"
  echo "--- $out/results.json summary ---"
  python3 - "$out/results.json" <<'PYEOF'
import json, sys, collections
data = json.load(open(sys.argv[1]))
rows = data if isinstance(data, list) else data.get("results", data)
print(f"total records: {len(rows) if hasattr(rows, '__len__') else 'n/a'}")
PYEOF
  echo "NOTE: no single committed table covers a full ground-truth run;" \
       "compare $out/results.json's disagreement count by hand against" \
       "whatever ROADMAP.md/WITNESS-*.md paragraph is being checked."
  stage_end truth
}

# --------------------------------------------------------------- --relift
run_relift() {
  stage_start relift
  local out=out/lift.repro
  echo "Private lift output at $out -- the live out/lift (possibly mid-rewrite" \
       "right now) is never touched by this stage."
  rm -rf "$out"
  python3 lifter.py --dir "$CORPUS" --corpus-dir "$CORPUS" --out "$out" \
      --jobs 12 --timeout 200 --force
  echo "lifter.py rc=$?"
  python3 lift_census.py --census-json "$LIFT_CENSUS_JSON" \
      --corpus-dir "$CORPUS" --out "$out" --report "$out/census_report_785"
  echo "lift_census.py rc=$?"
  cp "$out/census_report_785.md" LIFTER-785.relift.regen.md
  regen_diff LIFTER-785.md LIFTER-785.relift.regen.md "lifter census after a fresh --force relift"
  rm -rf out/lifted-tasks.repro
  python3 select_lifted.py --lift "$out" --out out/lifted-tasks.repro
  echo "select_lifted.py rc=$?"
  echo "run-ready tasks: $(ls out/lifted-tasks.repro 2>/dev/null | wc -l)"
  stage_end relift
}

# ---------------------------------------------------------------- --sweep
run_sweep() {
  stage_start sweep
  local tasks=out/lifted-tasks.repro
  if [ ! -d "$tasks" ]; then
    echo "WARNING: $tasks not found (run --relift first for a from-scratch" \
         "sweep). Falling back to the committed working set at" \
         "out/lifted-tasks, which is NOT guaranteed to match the tasks" \
         "COVERAGE-lifted-785.md's current header was swept over."
    tasks=out/lifted-tasks
  fi
  if [ ! -d "$tasks" ]; then
    echo "ERROR: neither out/lifted-tasks.repro nor out/lifted-tasks exists;" \
         "cannot sweep. Run --relift, or select_lifted.py --out out/lifted-tasks" \
         "against an existing out/lift first."
    stage_end sweep
    return 1
  fi
  python3 run_par.py --jobs 6 --tasks "$tasks" --out out/reproduce-sweep \
      --table COVERAGE-lifted-785.regen.md
  echo "run_par.py rc=$? (exit 1 is normal: some cells disagree or lack all seven)"
  python3 blockers.py COVERAGE-lifted-785.regen.md \
      --append COVERAGE-lifted-785.regen.md --replace
  echo "blockers.py rc=$?"
  regen_diff COVERAGE-lifted-785.md COVERAGE-lifted-785.regen.md "lifted-785 sweep"
  stage_end sweep
}

# --------------------------------------------------------------------- main
if [ $# -eq 0 ]; then
  usage
  exit 0
fi

DO_TESTS=0 DO_CENSUSES=0 DO_MATRIX=0 DO_FAMILIES=0 DO_TRUTH=0 DO_RELIFT=0 DO_SWEEP=0
for arg in "$@"; do
  case "$arg" in
    --tests) DO_TESTS=1 ;;
    --conformance) DO_CONFORMANCE=1 ;;
    --censuses) DO_CENSUSES=1 ;;
    --matrix) DO_MATRIX=1 ;;
    --families) DO_FAMILIES=1 ;;
    --truth) DO_TRUTH=1 ;;
    --relift) DO_RELIFT=1 ;;
    --sweep) DO_SWEEP=1 ;;
    --all) DO_TESTS=1 DO_CENSUSES=1 DO_MATRIX=1 DO_CONFORMANCE=1 DO_FAMILIES=1 DO_TRUTH=1 DO_RELIFT=1 DO_SWEEP=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown flag: $arg"; usage; exit 2 ;;
  esac
done

SCRIPT_T0=$(date +%s)
[ "$DO_TESTS" = 1 ] && run_tests
[ "$DO_CENSUSES" = 1 ] && run_censuses
[ "$DO_MATRIX" = 1 ] && run_matrix
[ "$DO_FAMILIES" = 1 ] && run_families
[ "$DO_TRUTH" = 1 ] && run_truth
[ "$DO_RELIFT" = 1 ] && run_relift
[ "$DO_SWEEP" = 1 ] && run_sweep
SCRIPT_T1=$(date +%s)

echo "=== reproduce.sh done in $((SCRIPT_T1 - SCRIPT_T0))s, $DIFF_COUNT table(s) differ ==="
exit $DIFF_COUNT
