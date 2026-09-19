#!/bin/bash
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
L=$HOME/.local/share/tjob/vllm-27b-3072.log; G=$HOME/.local/share/tjob/spec-gen-27b-3072.log
cd $HOME/tup/t || exit 1
stamp() { echo "$(date -u +%FT%TZ) $*" | tee -a $G; }
stamp "waiting for the 27B server"
for i in $(seq 1 180); do grep -q "Application startup complete" $L 2>/dev/null && break; grep -q "SERVE_EXIT" $L 2>/dev/null && { stamp "server exited before startup; GEN_DONE"; exit 1; }; sleep 10; done
grep -q "Application startup complete" $L || { stamp "server not up after 30 min; GEN_DONE"; exit 1; }
stamp "generate qwen3.8-27b-fp8"
python3 spec_experiment.py generate --model qwen3.8-27b-fp8 --host 127.0.0.1:11434 --seed 1 --num-ctx 8192 --num-predict 3072 --timeout 1800 --jobs 8 2>&1 | tee -a $G
stamp "generate rc=${PIPESTATUS[0]}"
# servers stay resident by request (2026-09-15); they are no longer killed here
stamp "generation done, servers left resident; GEN_DONE"
