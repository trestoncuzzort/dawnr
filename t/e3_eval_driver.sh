#!/bin/bash
cd ~/Projects/dawnr/t
H="$HOME"
KDIRS="$H/.cargo/bin:$H/.opam/default/bin:$H/.elan/bin:$H/.local/lean/bin:$H/.local/fstar/fstar/bin:$H/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$H/.local/verus/verus-x86-linux:$H/.local/dafny"
MODELS="raw-s0 raw-s1 raw-s2 graded-s0 graded-s1 graded-s2 all7-s0 all7-s1 all7-s2"
mkdir -p out/e3-grade
# 1. generate (3 parallel, CPU)
printf '%s\n' $MODELS | HF_HOME="$H/hf-cache" E3_THREADS=28 xargs -P 3 -L 1 bash -c '
  ~/e3-venv/bin/python gen_eval_cpu.py --model "out/e3-runs/$1/merged" --tag "e3eval-$1" \
    --split out/loop/split-v5.json --limit 30 --max-new 256 > "out/e3-runs/eval-gen-$1.log" 2>&1
  echo "[$(date -u +%H:%M:%SZ)] GEN-DONE $1"' _
echo "E3-EVAL-GEN-DONE $(date -u +%H:%M:%SZ)"
# 2. grade (3 parallel, needs the 7 provers on PATH; system python3 runs the engine)
printf '%s\n' $MODELS | xargs -P 3 -L 1 bash -c '
  PATH="'"$KDIRS"':$PATH" T_LEAN_BIN="'"$H"'/.local/lean/bin/lean" \
    python3 grade.py --replies "out/spec-experiment/e3eval-$1" --out "out/e3-grade/$1" --kernels dafny,verus,spark,framac,lean,rocq,fstar --min-kernels 1 > "out/e3-runs/eval-grade-$1.log" 2>&1
  echo "[$(date -u +%H:%M:%SZ)] GRADE-DONE $1"' _
echo "E3-EVAL-DONE $(date -u +%H:%M:%SZ)"
