#!/bin/bash
# Grade this machine's answer sets on the lab workstation (CPU only), 2026-09-17.
#   bash t/grade_lab.sh seeds     every qwen2.5-coder-14b seed's grade-in/ not yet graded
#   bash t/grade_lab.sh tags T1 T2 ...  those answer sets' grade-in/ (repairs, other generators)
#   bash t/grade_lab.sh heldout   the held-out answer sets' tasks/ (extract and tests run here first)
# Copies the tasks over, runs run_par.py there, copies kernels.md back. Checker events stream
# into this machine's T_WATCH so t lab's Live checks shows them. Needs key login, and the VPN when the
# workstation is only reachable through one (T_VPN_CMD).
set -u
# the whole script is one function, read in full before it runs: editing this file while a job
# runs cannot change what that job does
main() {
# Set T_LAB to user@host of a machine with the seven checkers installed and key login from here, or put the
# line T_LAB=user@host in t/lab-workstation.conf (which git ignores).
[ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
LAB=${T_LAB:?set T_LAB=user@host, or write it into t/lab-workstation.conf}
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
JOBS=${T_LAB_JOBS:-32}              # cells at once, over all the answer sets being graded together
SETS=${T_LAB_SETS:-4}               # answer sets at once: one small set cannot keep 120 threads busy
SE=t/out/spec-experiment
# The lab workstation has 502 GB of memory and a 252 GB RAM disk. Grading is small-file work (a lowered source
# per cell, a gnatprove work tree, why3 session files), so the whole working set lives in RAM and only
# kernels.md comes back. T_LAB_WORK=~/tup-grade puts it on disk again.
WORK=${T_LAB_WORK:-/dev/shm/tup-grade}
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o ServerAliveInterval=30"
REMOTE_EV='.cache/t-watch/home-grade.jsonl'

if ! $SSH "$LAB" true 2>/dev/null; then
  # unreachable: run T_VPN_CMD, if one is set, and wait up to 10 minutes for the workstation to answer
  echo "lab workstation not reachable${T_VPN_CMD:+, running T_VPN_CMD}"
  [ -n "${T_VPN_CMD:-}" ] && setsid sh -c "$T_VPN_CMD" >/dev/null 2>&1 &
  for i in $(seq 1 120); do sleep 5; $SSH "$LAB" true 2>/dev/null && break; done
  $SSH "$LAB" true || { echo "still cannot reach $LAB after 10 minutes"; exit 1; }
  echo "connected"
fi
$SSH "$LAB" "mkdir -p ~/.cache/t-watch $WORK && touch ~/$REMOTE_EV && cd ~/tup && git pull -q --ff-only || true"
if [ -n "${T_WATCH:-}" ]; then
  mkdir -p "$(dirname "$T_WATCH")"
  # remote pids mean nothing here, so drop them before t lab reads the line
  $SSH "$LAB" "tail -n0 -F ~/$REMOTE_EV" | stdbuf -oL -eL sed -u "s/\"pid\": [0-9]*, //" >> "$T_WATCH" &
  trap 'kill %1 2>/dev/null' EXIT
fi

par() {   # grade several answer sets at once, SETS of them, each with its share of the cells
  local n=0 t
  for t in "$@"; do
    grade "$t" grade-in &
    n=$((n + 1))
    if [ "$n" -ge "$SETS" ]; then wait -n 2>/dev/null || wait; n=$((n - 1)); fi
  done
  wait
}

grade() {  # tag, folder name inside the tag
  local T=$1 SUB=$2 D=$SE/$1
  [ -d "$D/$SUB" ] || { echo "== $T: no $SUB/ yet, skipped"; return 0; }
  [ -s "$D/kernels.md" ] && { echo "== $T: already graded"; return 0; }
  mkdir "$D/.grading" 2>/dev/null || { echo "== $T: being graded elsewhere, skipped"; return 0; }
  trap "rmdir '$D/.grading' 2>/dev/null; kill %1 2>/dev/null" EXIT
  echo "== $T: $(ls "$D/$SUB" | wc -l) tasks to the lab workstation"
  $SSH "$LAB" "mkdir -p $WORK/$T" && rsync -a --delete "$D/$SUB/" "$LAB:$WORK/$T/$SUB/" || return 1
  # T_LAB_RUN_PAR passes flags through to the driver. It is empty by default, so
  # every existing caller grades exactly as before. --no-cache is why it exists:
  # run_par.py caches by default for a table written outside the committed path,
  # and a comparison that claims one evaluator graded two answer sets in one
  # session has to have run the kernels for both of them (2026-09-19).
  $SSH "$LAB" "cd ~/tup && T_WATCH=\$HOME/$REMOTE_EV bash -lc 'python3 t/run_par.py --jobs $((JOBS / SETS)) --tasks $WORK/$T/$SUB --out $WORK/$T/kernels --table $WORK/$T/kernels.md ${T_LAB_RUN_PAR:-}'"
  rsync -a "$LAB:$WORK/$T/kernels.md" "$D/kernels.md" || return 1
  echo "== $T: kernels.md back"
  rmdir "$D/.grading" 2>/dev/null
}

case "${1:-seeds}" in
  # 2026-09-18: one mode instead of a step per round. Every answer set that has tasks worth grading and no
  # table yet, in one pass: a new set is picked up without anyone editing a list of tags.
  pending) mapfile -t pend < <(cd "$SE" && for d in */; do t=${d%/}; \
             [ -d "$t/grade-in" ] || continue; [ -s "$t/kernels.md" ] && continue; echo "$t"; done)
           [ ${#pend[@]} -eq 0 ] && { echo "== nothing to grade"; exit 0; }
           echo "== ${#pend[@]} answer sets to grade: ${pend[*]}"; par "${pend[@]}" ;;
  tags)    shift; par "$@" ;;
  matrix)  echo "== committed-tasks: $(ls t/tasks/*.t | wc -l) tasks to the lab workstation"
           $SSH "$LAB" "cd ~/tup && T_WATCH=\$HOME/$REMOTE_EV bash -lc 'python3 t/run_par.py --jobs $JOBS --out $WORK/matrix --table $WORK/AGREEMENT-lab.md'"
           rsync -a "$LAB:$WORK/AGREEMENT-lab.md" t/out/AGREEMENT-lab.md && tail -12 t/out/AGREEMENT-lab.md ;;
  seeds)   par $(for S in 1 2 3 4 5 6 7 8; do echo qwen2.5-coder-14b-v3-s$S; done) ;;
  heldout) shift 2>/dev/null || true
           # a held-out set has no grade-in/: nothing is pre-filtered, every answer is graded, which is what
           # makes it a measurement of the model rather than of the filter. Named tags may follow, so a later
           # round grades its own two sets without this list being edited (2026-09-18).
           for T in "${@:-phi4-mini-v3 qwen15b-base-v3 student-r4-v3 locallm-r4}"; do
             [ -d "$SE/$T/raw" ] || { echo "== $T: no answers yet, skipped"; continue; }
             [ -n "$(ls "$SE/$T/tasks"/*.json 2>/dev/null)" ] || { python3 t/spec_experiment.py extract --model $T --pool v3 &&
                                        python3 t/spec_experiment.py tests --model $T --pool v3; } || exit 1
             grade $T tasks || exit 1
           done ;;
esac
}
main "$@"; exit $?
