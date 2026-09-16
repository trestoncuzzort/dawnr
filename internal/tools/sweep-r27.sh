#!/bin/bash
# sweep r27, 2026-09-15: sweep alone at 16 jobs after wave Q (326 run-ready tasks), blockers, census. No commit here.
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
cd /home/tmcuzzort/tup || exit 1
S=${T_SCRATCH:-$HOME/.cache/t-gate}; mkdir -p "$S"
CORPUS=/home/tmcuzzort/tup/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth
stamp() { echo "$(date -u +%FT%TZ) $*"; }
cd t || exit 1
stamp "sweep r27, 16 jobs, alone"
python3 run_par.py --jobs 16 --tasks out/lifted-tasks --out out/sweep-785-r27 --table COVERAGE-lifted-785.md; stamp "run_par rc=$? (1 is normal)"
python3 blockers.py COVERAGE-lifted-785.md --append COVERAGE-lifted-785.md --replace; stamp "blockers rc=$?"
python3 mbpp_lifter_census.py --out COVERAGE-mbpp-dfy-lifter.md; stamp "census rc=$?"
grep -m1 "^Headline" COVERAGE-mbpp-dfy-lifter.md
stamp "sweep r27 done"
