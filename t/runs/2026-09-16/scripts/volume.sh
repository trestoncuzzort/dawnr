#!/bin/bash
# several sampled 27B answer sets on pool v3; grade only test-passing, new tasks
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
export T_WATCH=$HOME/.cache/t-watch/events.jsonl
cd $HOME/tup/t || exit 1
S=<scratch>/volume
stamp() { echo "$(date -u +%FT%TZ) $*"; }
python3 $S/pick.py out/spec-experiment/qwen3.8-27b-fp8 > /dev/null
python3 $S/pick.py out/spec-experiment/qwen3.8-27b-fp8-v3
for N in 2 3 4 5 6 7 8 9; do
  T=qwen3.8-27b-fp8-v3-s$N; D=out/spec-experiment/$T
  stamp "set $N generate"; python3 spec_experiment.py generate --model qwen3.8-27b-fp8 --tag $T --pool v3 --prompt v3 --host 127.0.0.1:11434 --seed $N --temperature 0.7 --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 8 2>&1 | tail -2
  python3 spec_experiment.py extract --model $T --pool v3 2>&1 | tail -1
  python3 spec_experiment.py tests --model $T --pool v3 2>&1 | tail -1
  python3 $S/pick.py $D
  stamp "set $N kernels"; python3 run_par.py --jobs 12 --tasks $D/grade-in --out $D/kernels --table $D/kernels.md 2>&1 | tail -1
done
stamp VOLUME_DONE
