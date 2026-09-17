#!/bin/bash
# Grade answer sets on this machine, from the last seed backwards, while t/grade_lab.sh works forwards on the
# lab workstation. Both claim a set with <tag>/.grading, so neither grades what the other has. 2026-09-17.
set -u
# the whole script is one function, read in full before it runs: editing this file while a job
# runs cannot change what that job does
main() {
SE=t/out/spec-experiment
JOBS=${T_JOBS:-6}                  # 14 GB of memory shared with Ollama
for S in 8 7 6 5 4 3 2 1; do
  T=qwen2.5-coder-14b-v3-s$S; D=$SE/$T
  [ -d "$D/grade-in" ] || continue
  [ -s "$D/kernels.md" ] && continue
  mkdir "$D/.grading" 2>/dev/null || { echo "== $T: being graded elsewhere, skipped"; continue; }
  trap "rmdir '$D/.grading' 2>/dev/null" EXIT
  echo "== $T: $(ls "$D/grade-in" | wc -l) tasks on this machine"
  # run_par.py exits 1 whenever any task disagrees, which is the normal case; the table is the result
  python3 t/run_par.py --jobs "$JOBS" --tasks "$D/grade-in" --out "$D/kernels" --table "$D/kernels.md"
  [ -s "$D/kernels.md" ] || { rmdir "$D/.grading"; exit 1; }
  rmdir "$D/.grading"; echo "== $T: kernels.md back"
done
}
main "$@"; exit $?
