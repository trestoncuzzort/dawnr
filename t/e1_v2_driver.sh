#!/bin/bash
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache"
echo "V2-POSTFIX-START $(date -u +%H:%M:%SZ)" >> out/E1PAIRS2-postfix.log
python3 -I e1_pairs_gate2.py run out/e1-pairs-v2-pf --jobs 8 --flake 3 >> out/E1PAIRS2-postfix.log 2>&1
echo "V2-POSTFIX-ALL-DONE $(date -u +%H:%M:%SZ)" >> out/E1PAIRS2-postfix.log
