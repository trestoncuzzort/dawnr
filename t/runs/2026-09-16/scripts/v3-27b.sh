#!/bin/bash
# 27B on pool v3 / prompt v3 (strings, seq of seq), thinking off, 3072 tokens; server stays resident
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
cd $HOME/tup/t || exit 1
M=qwen3.8-27b-fp8; T=qwen3.8-27b-fp8-v3; D=out/spec-experiment/$T
stamp() { echo "$(date -u +%FT%TZ) $*"; }
stamp generate; python3 spec_experiment.py generate --model $M --tag $T --pool v3 --prompt v3 --host 127.0.0.1:11434 --seed 1 --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 8 2>&1 | tail -5
stamp extract; python3 spec_experiment.py extract --model $T --pool v3 2>&1 | tail -15
stamp tests;   python3 spec_experiment.py tests   --model $T --pool v3 2>&1 | tail -8
stamp kernels; python3 run_par.py --jobs 8 --tasks $D/tasks --out $D/kernels --table $D/kernels.md 2>&1 | grep -v -E '^\s+\S+ x [a-z]+' | tail -12
stamp table;   python3 spec_experiment.py table --model $T --pool v3 --out SPEC-EXPERIMENT-mbpp-$T.md 2>&1 | tail -14
stamp V3_DONE
