#!/bin/bash
# stages for the qwen3.8-27b-fp8 round (thinking off, 3072 tokens): extract, tests, kernels, table.
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
cd $HOME/tup/t || exit 1
M=qwen3.8-27b-fp8; D=out/spec-experiment/$M
stamp() { echo "$(date -u +%FT%TZ) $*"; }
stamp extract; python3 spec_experiment.py extract --model $M 2>&1 | tail -15
stamp tests;   python3 spec_experiment.py tests   --model $M 2>&1 | tail -8
stamp kernels; python3 run_par.py --jobs 16 --tasks $D/tasks --out $D/kernels --table $D/kernels.md 2>&1 | grep -v -E '^\s+\S+ x [a-z]+' | tail -12
stamp table;   python3 spec_experiment.py table   --model $M --out SPEC-EXPERIMENT-mbpp-qwen3.8-27b-fp8.md 2>&1 | tail -14
stamp STAGES3072_DONE
