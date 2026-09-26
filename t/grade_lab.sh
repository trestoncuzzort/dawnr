#!/bin/bash
# Grade this machine's answer sets on the lab workstation (CPU only), 2026-09-17.
#   bash t/grade_lab.sh seeds     every qwen2.5-coder-14b seed's grade-in/ not yet graded
#   bash t/grade_lab.sh tags T1 T2 ...  those answer sets' grade-in/ (repairs, other generators)
#   bash t/grade_lab.sh heldout   the held-out answer sets' tasks/ (extract and tests run here first)
# Copies the tasks over, runs run_par.py there, copies kernels.md back. Checker events stream
# into this machine's T_WATCH so locallm's Live checks shows them. Needs key login, and the VPN when the
# workstation is only reachable through one (T_VPN_CMD).
set -u
# the whole script is one function, read in full before it runs: editing this file while a job
# runs cannot change what that job does
main() {
# Set T_LAB to user@host of a machine with the seven checkers installed and key login from here, or put the
# line T_LAB=user@host in t/lab-workstation.conf (which git ignores). T_LAB=local grades on this machine
# through the same steps (t/lab_mode.sh, 2026-09-26). An environment T_LAB wins over the conf, so
# `T_LAB=local bash t/grade_lab.sh matrix` works beside a conf that names the workstation.
[ -z "${T_LAB:-}" ] && [ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
LAB=${T_LAB:?set T_LAB=user@host or T_LAB=local, or write it into t/lab-workstation.conf}
. t/lab_mode.sh
# The lab workstation has 120 threads and its CPUs are ours; only its GPUs are off limits. gnatprove runs one
# core per cell and SPARK is 44 percent of all proof time, so cells, not threads, are the limit: with 16 cells
# only 16 cores worked. Cells are cheap in memory (z3 and one prover each), so the default is most of the
# machine; Frama-C spawns 4 provers per cell of its own (verifiers/framac.py PAR), which is why this is not 120.
# 2026-09-18, measured on the APPS sets: 64 cells drew 216 of this machine's 120 cores and the load average
# sat at 2.1x the core count, because a SPARK cell is not one core -- gnatprove keeps a gnatwhy3 tree alive, and
# those sets are loop-heavy, so a cell averages 3.4 cores. Oversubscription is not merely slow: the wall-clock
# backstop in verifiers/spark.py then fires on cells that would prove alone, and a timeout is not a verdict
# (t/preflight.py refuses any clean answer resting on one). 32 cells is about 110 cores, which leaves the other
# users of a shared machine a little room as well.
JOBS=${T_LAB_JOBS:-$(default_jobs)}   # cells at once, over all the answer sets being graded together (8 here, 32 on the lab)
SETS=${T_LAB_SETS:-$(default_sets)}   # answer sets at once: one small set cannot keep 120 threads busy (1 here, 4 on the lab)
SE=t/out/spec-experiment
# The lab workstation has 502 GB of memory and a 252 GB RAM disk. Grading is small-file work (a lowered source
# per cell, a gnatprove work tree, why3 session files), so the whole working set lives in RAM and only
# kernels.md comes back. T_LAB_WORK=~/tup-grade puts it on disk again.
WORK=${T_LAB_WORK:-$(default_work_dir)}
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30"
REMOTE_EV='.cache/t-watch/home-grade.jsonl'

if ! reachable; then
  # unreachable: run T_VPN_CMD, if one is set, and wait up to 10 minutes for the workstation to answer
  echo "lab workstation not reachable${T_VPN_CMD:+, running T_VPN_CMD}"
  # setsid is util-linux and macOS has none at all -- github.com/jerrykuch/ersatz-setsid
  # exists only because of that, and Homebrew's util-linux is keg-only so it never
  # reaches PATH either. nohup is not the substitute: it only sets SIGHUP to be ignored
  # and starts no new session (keith.github.io/xcode-man-pages/nohup.1.html), so a ^C in
  # this terminal would still reach the VPN. python3 has to be present to run anything in
  # this repository anyway, and os.setsid() is the syscall setsid(1) wraps. The fork is
  # not optional: setsid(1) "calls fork(2) if already a process group leader"
  # (man7.org/linux/man-pages/man1/setsid.1.html), and a background job started under job
  # control is one, where a bare os.setsid() would raise PermissionError instead.
  if [ -n "${T_VPN_CMD:-}" ]; then
    if command -v setsid >/dev/null 2>&1; then
      setsid sh -c "$T_VPN_CMD" >/dev/null 2>&1 &
    else
      python3 -c 'import os,sys
if os.fork(): raise SystemExit
os.setsid()
os.execvp("sh", ["sh", "-c", sys.argv[1]])' "$T_VPN_CMD" >/dev/null 2>&1 &
    fi
  fi
  for i in $(seq 1 120); do sleep 5; $SSH "$LAB" true 2>/dev/null && break; done
  $SSH "$LAB" true || { echo "still cannot reach $LAB after 10 minutes"; exit 1; }
  echo "connected"
fi
remote "mkdir -p ~/.cache/t-watch $WORK && touch ~/$REMOTE_EV"

# JOBS used to be 32 whatever else was on the machine. On 2026-09-19 ten
# generation workers, a 7B model and 32 grading cells put the load average at 80
# on a 120-core box shared with another user, and the ssh carrying this script
# timed out mid-grade: the kernels survived as orphans and the table was never
# written. Read the machine first and take what is actually free.
BUSY=$(remote "cut -d' ' -f1 /proc/loadavg; nproc; ps -eo cmd | grep -cE '[l]oop_locallm.py generate|[l]oop_generate.py'" 2>/dev/null | tr '\n' ' ')
# read, not `set --`: `set --` replaces the POSITIONAL PARAMETERS, and this
# script's mode is $1. From a6acacb until this was found on 2026-09-20,
# `set -- $BUSY` overwrote "heldout" with the load average, the case below
# matched no branch, and the script exited 0 having graded nothing. A grading
# command that reports success without grading is the worst failure available
# to this project: every caller believed it had a table. Same root cause as the
# gen_fleet.sh flag loss fixed in 75a43fa the same day.
read -r LOAD CORES OURS <<<"$BUSY"
LOAD=${LOAD:-0}; CORES=${CORES:-120}; OURS=${OURS:-0}
HEADROOM=$(awk -v c="$CORES" -v l="$LOAD" 'BEGIN{h=int(c-l); print (h>0)?h:0}')
if [ "${OURS:-0}" -gt 0 ]; then
  echo "NOTE: $OURS of our generation workers are still running on the grading machine."
  echo "      Generation is GPU work and grading is CPU work, but they share the box and"
  echo "      the connection. Consider waiting; continuing with fewer cells."
fi
# A SPARK cell averages 3.4 cores, so cells, not threads, are the budget.
FIT=$(( HEADROOM / 4 ))
[ "$FIT" -lt 4 ] && FIT=4
if [ "$FIT" -lt "$JOBS" ]; then
  echo "load $LOAD on $CORES cores: taking $FIT cells instead of $JOBS"
  JOBS=$FIT
fi
# The pull used to be `|| true`, which is how the grading machine ran 19 commits
# behind origin with 109 dirty entries for an unknown number of rounds while
# every log line said the round had started normally (2026-09-19). A grader that
# is not the tree you think it is invalidates the comparison, not the run, so
# this reports loudly and continues: the answers are still graded, and the state
# that graded them is printed where the operator sees it.
# Locally the grading machine IS this tree: nothing to pull, and the drift warning does not apply.
if ! lab_is_local && ! remote "cd ~/tup && git pull -q --ff-only" 2>/tmp/t-grade-pull.$$; then
  echo "WARNING: the grading machine did not update. It is grading with:"
  remote "cd ~/tup && echo '  HEAD '\$(git rev-parse --short HEAD) && echo '  dirty entries '\$(git status --porcelain | wc -l)"
  # -n 2, not -2: BSD head documents only -n count, and this line runs here, not on the lab
  # (keith.github.io/xcode-man-pages/head.1.html). GNU head prints the same two lines either way.
  echo "  reason: $(head -n 2 /tmp/t-grade-pull.$$ | tr '\n' ' ')"
  echo "  a comparison across evaluators is not a comparison: regrade a baseline beside the new set."
fi
rm -f /tmp/t-grade-pull.$$
if [ -n "${T_WATCH:-}" ]; then
  mkdir -p "$(dirname "$T_WATCH")"
  # remote pids mean nothing here, so drop them before locallm reads the line.
  # This half of the pipeline runs HERE, not through the ssh, so the line buffering has to
  # exist on whatever machine is showing the window -- and both spellings this used to
  # hardcode are GNU. stdbuf is coreutils 7.5+ (08/2009) and sed -u is GNU sed 3.02.80+
  # (www.in-ulm.de/~mascheck/various/buffering/, the survey of this problem class); a BSD
  # userland has neither, and stdbuf cannot even be ported, since it works by LD_PRELOADing
  # a setvbuf call. BSD/macOS sed spells the same capability -l, "Make output line buffered"
  # (keith.github.io/xcode-man-pages/sed.1.html). Rejected that survey's portable option 4,
  # a shell read loop in place of sed: bash's ${v//pat/rep} is a glob and replaces EVERY
  # match, where s/// without g replaces only the first, so an event carrying two pid fields
  # would reach T_WATCH different from Linux. Probed by running it rather than by uname,
  # because the only question that matters is whether this sed takes the flag (a Mac may
  # have Homebrew's gsed first on PATH; a Linux box may have busybox sed).
  if printf '' | sed -u 's/a/a/' >/dev/null 2>&1; then
    FILTER=(sed -u)
    command -v stdbuf >/dev/null 2>&1 && FILTER=(stdbuf -oL -eL sed -u)
  elif printf '' | sed -l 's/a/a/' >/dev/null 2>&1; then
    FILTER=(sed -l)
  else
    # Refuse by name. Without line buffering sed block-buffers into T_WATCH in 4K chunks and
    # locallm's Live checks stays empty for most of a grade, which reads as a dead grader.
    echo "T_WATCH is set, but nothing here can stream line by line: need GNU stdbuf with sed -u, or BSD sed -l."
    echo "  unset T_WATCH to grade without the live stream."
    exit 1
  fi
  remote "tail -n0 -F ~/$REMOTE_EV" | "${FILTER[@]}" "s/\"pid\": [0-9]*, //" >> "$T_WATCH" &
  trap 'kill %1 2>/dev/null' EXIT
fi

# `wait -n` arrived in bash 4.3 ("The `wait' builtin has a new `-n' option to wait for the next
# child to change status", git.savannah.gnu.org/cgit/bash.git/tree/NEWS?h=bash-4.3), and bash
# 3.2 rejects it as an invalid option. The bare `|| wait` below already caught that, but it then
# subtracted one from n after a wait that had already reaped every job, so on a Mac the loop
# graded one set at a time for the rest of the run. Decide on the version, not on the exit
# status: on bash 4.3+ a nonzero `wait -n` means that answer set FAILED, which has to go on
# meaning what it means here. BASH_VERSINFO has been set since bash 2.0.
WAIT_N=no
[ "${BASH_VERSINFO[0]}" -gt 4 ] && WAIT_N=yes
[ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -ge 3 ] && WAIT_N=yes
# `wait -n -p VAR` (bash 5.1) names the job whose status came back, which is what lets
# par() below say WHICH set failed and still wait for the rest by pid.
WAIT_NP=no
[ "${BASH_VERSINFO[0]}" -gt 5 ] && WAIT_NP=yes
[ "${BASH_VERSINFO[0]}" -eq 5 ] && [ "${BASH_VERSINFO[1]}" -ge 1 ] && WAIT_NP=yes

lab_quiet() {  # t/stall_check.py on the grading machine: nothing of ours stopped, no orphan prover
  # The check runs where the processes are. A missing checker is a refusal, not a pass: on
  # 2026-09-20 the cpu-yield watcher froze the grader and exited without resuming it, and 26
  # orphan z3s ran for a day, while every log line read normally (t/RUN-NEXT-locallm-r12.md, A5).
  # The r12 build adds t/stall_check.py; until the grading machine has it, grading is refused
  # by name rather than started blind.
  local out rc
  out=$(remote "cd ~/tup && if [ -f t/stall_check.py ]; then python3 t/stall_check.py; else echo 'REFUSED: t/stall_check.py is missing on the grading machine (the r12 build adds it; pull there first)'; exit 3; fi" 2>&1); rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "== the grading machine is not quiet (stall_check exit $rc):"
    printf '   %s\n' "$out"
    return 1
  fi
  return 0
}

par() {   # grade several answer sets at once, SETS of them, each with its share of the cells
  # Every set's exit status is collected and the worst one is returned. Until 2026-09-25 this
  # ended in a bare `wait`, whose "return status is zero" whatever the jobs did, and the
  # throttle's `wait -n || wait` reaped a failure without recording it, so `tags` and `pending`
  # exited 0 after a failed set (gnu.org/software/bash/manual/html_node/Job-Control-Builtins.html).
  local pids=() running=0 failed=0 t rc done_pid p keep
  for t in "$@"; do
    grade "$t" grade-in &
    pids+=("$!"); running=$((running + 1))
    if [ "$running" -ge "$SETS" ]; then
      if [ "$WAIT_NP" = yes ]; then
        wait -n -p done_pid "${pids[@]}"; rc=$?
        [ "$rc" -ne 0 ] && { failed=1; echo "== a set failed (pid ${done_pid:-?}, status $rc)"; }
        keep=(); for p in "${pids[@]}"; do [ "$p" = "${done_pid:-}" ] || keep+=("$p"); done; pids=("${keep[@]}")
        running=$((running - 1))
      elif [ "$WAIT_N" = yes ]; then
        wait -n; rc=$?                 # bash 4.3-5.0: the status, but not which job; grade() names it itself
        [ "$rc" -ne 0 ] && { failed=1; echo "== a set failed (status $rc)"; }
        running=$((running - 1))
      else                             # bash 3.2 has no wait -n: one batch of SETS at a time, each waited by pid
        for p in "${pids[@]}"; do wait "$p" || failed=1; done; pids=(); running=0
      fi
    fi
  done
  if [ "$WAIT_NP" = yes ] || [ "$WAIT_N" = no ]; then
    for p in "${pids[@]}"; do wait "$p" || failed=1; done
  else
    while [ "$running" -gt 0 ]; do wait -n; rc=$?; [ "$rc" -ne 0 ] && failed=1; running=$((running - 1)); done
  fi
  [ "$failed" -ne 0 ] && echo "== at least one answer set was NOT graded; no table from it is trustworthy"
  return "$failed"
}

grade() {  # tag, folder name inside the tag
  local T=$1 SUB=$2 D=$SE/$1 rc
  [ -d "$D/$SUB" ] || { echo "== $T: no $SUB/ yet, skipped"; return 0; }
  [ -s "$D/kernels.md" ] && { echo "== $T: already graded"; return 0; }
  mkdir "$D/.grading" 2>/dev/null || { echo "== $T: being graded elsewhere, skipped"; return 0; }
  trap "rmdir '$D/.grading' 2>/dev/null; kill %1 2>/dev/null" EXIT
  lab_quiet || { rmdir "$D/.grading" 2>/dev/null; return 2; }
  echo "== $T: $(ls "$D/$SUB" | wc -l) tasks to the lab workstation"
  # A table left in $WORK by an earlier run must not come back as this run's: it is removed
  # before run_par starts, and copied back only when run_par exits 0 and wrote it.
  remote "mkdir -p $WORK/$T && rm -f $WORK/$T/kernels.md" && store -a --delete "$D/$SUB/" "$LAB:$WORK/$T/$SUB/" \
    || { rmdir "$D/.grading" 2>/dev/null; return 1; }
  # T_LAB_RUN_PAR passes flags through to the driver. It is empty by default, so
  # every existing caller grades exactly as before. --no-cache is why it exists:
  # run_par.py caches by default for a table written outside the committed path,
  # and a comparison that claims one evaluator graded two answer sets in one
  # session has to have run the kernels for both of them (2026-09-19).
  # T_SPARK_JOBS=1: the cell budget above is ~4 cores a cell, measured 2026-09-18 with gnatprove
  # serial. On 2026-09-19 verifiers/spark.py began running gnatprove -j8 inside every cell, so a
  # SPARK cell became up to 8 provers inside a 4-core budget, and on 2026-09-21 24 cells put the
  # load average at 351 on 120 cores; the table graded that way the day before carried 4 SPARK
  # cells "timeout (FLAKED)" that verify when regraded. BenchExec's rule (Beyer, Loewe, Wendler,
  # "Reliable Benchmarking: Requirements and Solutions", STTT 2019; github.com/sosy-lab/benchexec)
  # is that a run's budget has to cover its subprocesses, and spark.py's own comment names -j1 as
  # what a lab sweep should set. It leaves every verdict byte-identical (spark.py, MEASURED); only
  # wall clock changes. An explicit T_SPARK_JOBS in the environment still wins.
  remote "cd ~/tup && T_WATCH=\$HOME/$REMOTE_EV T_SPARK_JOBS=${T_SPARK_JOBS:-1} bash -lc 'python3 t/run_par.py --jobs $((JOBS / SETS)) --tasks $WORK/$T/$SUB --out $WORK/$T/kernels --table $WORK/$T/kernels.md ${T_LAB_RUN_PAR:-}'"; rc=$?
  # run_par exits 0 on full agreement and 1 on a finding: a DISAGREEMENT is a verdict and the
  # table is written either way (t/run_par.py main returns 0 if all_ok else 1); 2 is a refusal
  # before any cell ran and nothing was written. The first queue run (2026-09-25) discarded a
  # finished 247-cell table because 1 was read as "no table".
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
    echo "== $T: run_par exited $rc on the grading machine; no table copied back"
    rmdir "$D/.grading" 2>/dev/null
    return 1
  fi
  fetch -a "$LAB:$WORK/$T/kernels.md" "$D/kernels.md" \
    || { echo "== $T: run_par exited $rc but left no $WORK/$T/kernels.md"; rmdir "$D/.grading" 2>/dev/null; return 1; }
  echo "== $T: kernels.md back"
  rmdir "$D/.grading" 2>/dev/null
}

case "${1:-seeds}" in
  # 2026-09-18: one mode instead of a step per round. Every answer set that has tasks worth grading and no
  # table yet, in one pass: a new set is picked up without anyone editing a list of tags.
  # mapfile is a bash 4.0 builtin and bash 3.2 has no such command, so on a Mac this line used
  # to die with "mapfile: command not found" and then take the whole script down on the next
  # ${#pend[@]} under set -u. Its own documentation says not to use it if portability matters at
  # all, and that it can do nothing a read loop cannot (bash-hackers.gabe565.com/commands/builtin/mapfile/).
  # The loop is the form from mywiki.wooledge.org/BashFAQ/001: IFS= stops read trimming leading
  # and trailing whitespace so a tag with spaces stays one element, -r keeps a backslash
  # literal, and `|| [ -n "$p" ]` takes a last line that has no newline -- which is mapfile -t
  # exactly. Checked against mapfile -t on empty input, one line, a name with spaces, a missing
  # final newline and a backslash: same count, same elements, and an empty array either way.
  # Process substitution rather than a pipe, for the reason mapfile needed it too: a pipe builds
  # the array in a subshell and leaves pend empty out here.
  pending) pend=(); p=
           while IFS= read -r p || [ -n "$p" ]; do pend+=("$p"); done < <(cd "$SE" && for d in */; do t=${d%/}; \
             [ -d "$t/grade-in" ] || continue; [ -s "$t/kernels.md" ] && continue; echo "$t"; done)
           [ ${#pend[@]} -eq 0 ] && { echo "== nothing to grade"; exit 0; }
           echo "== ${#pend[@]} answer sets to grade: ${pend[*]}"; par "${pend[@]}" ;;
  tags)    shift; par "$@" ;;
  matrix)  echo "== committed-tasks: $(ls t/tasks/*.t | wc -l) tasks to the lab workstation"
           lab_quiet || exit 2
           # the same T_SPARK_JOBS=1 as grade(): the committed matrix graded at -j8 inside
           # every SPARK cell is the table that carried the timeout cells of 2026-09-21
           # run_par exits 1 on a finding with the table written (see grade()); only 2 means no table
           remote "cd ~/tup && rm -f $WORK/AGREEMENT-lab.md && T_WATCH=\$HOME/$REMOTE_EV T_SPARK_JOBS=${T_SPARK_JOBS:-1} bash -lc 'python3 t/run_par.py --jobs $JOBS --out $WORK/matrix --table $WORK/AGREEMENT-lab.md'"; rc=$?
           if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then echo "== matrix: run_par exited $rc on the grading machine; no table copied back"; exit 1; fi
           fetch -a "$LAB:$WORK/AGREEMENT-lab.md" t/out/AGREEMENT-lab.md && tail -12 t/out/AGREEMENT-lab.md ;;
  seeds)   par $(for S in 1 2 3 4 5 6 7 8; do echo qwen2.5-coder-14b-v3-s$S; done) ;;
  heldout) shift 2>/dev/null || true
           # a held-out set has no grade-in/: nothing is pre-filtered, every answer is graded, which is what
           # makes it a measurement of the model rather than of the filter. Named tags may follow, so a later
           # round grades its own two sets without this list being edited (2026-09-18).
           # "${@:-a b c d}" expands to ONE word holding all four names, so with
           # no tags the loop ran once against a tag that cannot exist and printed
           # "no answers yet, skipped" (issue #24). The tagged form always worked,
           # which is why every run in this session succeeded and nobody noticed.
           heldout=("$@")
           [ ${#heldout[@]} -eq 0 ] && heldout=(phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4)
           for T in "${heldout[@]}"; do
             [ -d "$SE/$T/raw" ] || { echo "== $T: no answers yet, skipped"; continue; }
             # The pool comes from the raw records themselves. This line hard-coded --pool v3,
             # which is right for the held-out arms and wrong for every train-side tag (pool v5
             # or v6) that was ever passed here; one set must name exactly one pool.
             POOL=$(python3 - "$SE/$T/raw" <<'PY'
import glob, json, os, sys
seen = set()
for f in glob.glob(os.path.join(sys.argv[1], "*.json")):
    try:
        seen.add(str(json.load(open(f, encoding="utf-8")).get("pool_version")))
    except ValueError:
        seen.add("torn:" + os.path.basename(f))
print(",".join(sorted(seen)))
PY
)
             case "$POOL" in
               v[0-9]|v[0-9][0-9]) ;;
               *) echo "== $T: the raw records name pool '$POOL'; one pool per answer set is required, refusing to extract"; exit 1 ;;
             esac
             [ -n "$(ls "$SE/$T/tasks"/*.json 2>/dev/null)" ] || { python3 t/spec_experiment.py extract --model $T --pool $POOL &&
                                        python3 t/spec_experiment.py tests --model $T --pool $POOL; } || exit 1
             grade $T tasks || exit 1
           done ;;
esac
}
main "$@"; exit $?
