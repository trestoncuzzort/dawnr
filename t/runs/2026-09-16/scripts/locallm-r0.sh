#!/bin/bash
# locallm round 0 on the clean corpus: train, answer the held-out problems, grade like any model
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
export T_WATCH=$HOME/.cache/t-watch/events.jsonl CUDA_VISIBLE_DEVICES=2
cd $HOME/tup/t || exit 1
PY=$HOME/.venv-train/bin/python; T=locallm-r0; D=out/spec-experiment/$T
stamp() { echo "$(date -u +%FT%TZ) $*"; }
stamp train;    $PY loop_locallm.py train --steps 3000 --layers 6 --heads 8 --width 256 --batch 16 --block 512 2>&1 | grep -E "^step|model:|corpus:|YOUR MODEL" 
stamp generate; $PY loop_locallm.py generate --temperature 0.5 --tag $T 2>&1 | tail -1
stamp extract;  python3 spec_experiment.py extract --model $T --pool v3 2>&1 | tail -1
stamp tests;    python3 spec_experiment.py tests --model $T --pool v3 2>&1 | tail -1
stamp kernels;  python3 run_par.py --jobs 8 --tasks $D/tasks --out $D/kernels --table $D/kernels.md 2>&1 | tail -1
stamp LOCALLM_R0_DONE
