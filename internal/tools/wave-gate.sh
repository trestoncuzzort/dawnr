#!/bin/bash
# usage: wave-gate.sh <name>   (conformance full run, matrix diff vs the banked AGREEMENT.md, reproduce.sh --tests)
N=${1:?name}
export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$PATH
cd $HOME/tup/t || exit 1
S=${T_SCRATCH:-$HOME/.cache/t-gate}; mkdir -p "$S"
bash -n reproduce.sh || { echo "reproduce.sh SYNTAX ERROR"; exit 2; }
cp AGREEMENT.md $S/AGREEMENT.pre-$N.md
echo "$(date -u +%FT%TZ) conformance"
python3 conformance.py --jobs 16 --flake 3 --out CONFORMANCE.md; echo "conformance rc=$?"
echo "PASS cells: $(grep -o '\[PASS\]' CONFORMANCE.md | wc -l)  FAIL cells: $(grep -o '\[FAIL\]' CONFORMANCE.md | wc -l)"
grep -n "FAIL\]" CONFORMANCE.md | grep -v "^3:" | cut -d'|' -f2 | tr -d ' ' | sort | tr '\n' ' '; echo
echo "$(date -u +%FT%TZ) matrix"
python3 run_par.py --jobs 16; echo "matrix rc=$?"
diff <(tail -n +2 $S/AGREEMENT.pre-$N.md) <(tail -n +2 AGREEMENT.md) > $S/agreement-$N.diff; echo "matrix diff lines: $(wc -l < $S/agreement-$N.diff)"; cut -c1-200 $S/agreement-$N.diff
echo "$(date -u +%FT%TZ) tests"
bash reproduce.sh --tests 2>&1 | grep -E "rc=|Traceback|round trip|stage|FAIL|Error"
echo "$(date -u +%FT%TZ) done"
