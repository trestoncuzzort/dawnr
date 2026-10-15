#!/bin/bash
# authoritative v2 PASS 2 (second independent rerun). Propagates Python's exit status so unit success reflects
# the run's exit (not an unconditional ALL-DONE). Launch with: systemd-run --user -p MemoryMax=16G --unit=e1v2pass2 ...
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache"
echo "V2-PASS2-START $(date -u +%H:%M:%SZ)" >> out/E1PAIRS2-pass2.log
python3 -I e1_pairs_gate2.py run out/e1-pairs-v2-pass2 --jobs 8 --flake 3 >> out/E1PAIRS2-pass2.log 2>&1
rc=$?
echo "V2-PASS2-DONE rc=$rc $(date -u +%H:%M:%SZ)" >> out/E1PAIRS2-pass2.log
exit "$rc"
