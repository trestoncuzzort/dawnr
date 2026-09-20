#!/bin/bash
# Finish the three seed arms left mid-grade on 2026-09-19 and score them.
# One command. Safe to re-run: it regrades only what has no table.
#
#   bash t/finish_seeds.sh
#
# What it does: waits for /tmp/finish_tables.sh on the lab (if still running),
# copies each arm's kernels.md back, regrades anything missing from scratch,
# runs the specification check, and prints the scoreboard with the three seeds
# beside Phi. The answers themselves are already generated, 232 per arm.
set -u
cd "$(dirname "$0")/.."
[ -f t/lab-workstation.conf ] && . t/lab-workstation.conf
LAB=${T_LAB:?set T_LAB in t/lab-workstation.conf}
SSH="ssh -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=30"
ARMS="locallm-r9 locallm-r9-seed7 locallm-r9-seed42"

echo "== waiting for the lab to finish assembling tables (ctrl-c to skip) =="
for i in $(seq 1 120); do
  $SSH "$LAB" 'test -f ~/tup/t/out/tables.done' 2>/dev/null && { echo "tables.done"; break; }
  sleep 30
done

for T in $ARMS; do
  rmdir "t/out/spec-experiment/$T/.grading" 2>/dev/null
  if $SSH "$LAB" "test -s /dev/shm/tup-grade/$T/kernels.md" 2>/dev/null; then
    rsync -a "$LAB:/dev/shm/tup-grade/$T/kernels.md" "t/out/spec-experiment/$T/kernels.md"
    echo "$T: table copied back"
  fi
  if [ ! -s "t/out/spec-experiment/$T/kernels.md" ]; then
    echo "$T: no table, grading from scratch at reduced parallelism"
    T_LAB_JOBS=16 T_LAB_SETS=1 bash t/grade_lab.sh heldout "$T" || exit 1
  fi
done

python3 t/spec_check.py $ARMS --pool v5 --n 100 --only clean \
  --out "$PWD/t/SPEC-CHECK-seeds-2026-09-19.md" || exit 1

python3 t/score_heldout.py phi4-mini-eval2-2026-09-19 locallm-r7b-greedy locallm-r8 \
  locallm-r7b-headed2 $ARMS | tee t/out/score-seeds.md
echo
echo "Three seeds of one recipe. If all three land near 3 clean, the tie is not luck."
