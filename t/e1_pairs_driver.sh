#!/bin/bash
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache"
mkdir -p out/e1-pairs-full
echo "E1-PAIRS-START $(date -u +%H:%M:%SZ)" >> out/E1PAIRS-full.log
python3 -I e1_pairs_gate.py run out/e1-pairs-full --jobs 8 --flake 3 >> out/E1PAIRS-full.log 2>&1
echo "E1-PAIRS-ALL-DONE $(date -u +%H:%M:%SZ)" >> out/E1PAIRS-full.log
