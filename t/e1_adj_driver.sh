#!/bin/bash
cd ~/Projects/dawnr/t
export HF_HOME="$HOME/hf-cache" E1_SCOPE=all
V=~/e3-venv/bin/python
[ -f out/E1MAN-vcd.json ] || $V e1_full_adjudicate.py manifest vericoding/dafny vcd 12
for tag in hev auto vcd df; do
  echo "[$(date -u +%H:%M:%SZ)] ADJ START $tag"
  $V e1_full_adjudicate.py adjudicate "$tag" 18 full-pop
  echo "[$(date -u +%H:%M:%SZ)] ADJ DONE $tag"
done
echo "E1-ADJ-ALL-DONE $(date -u +%H:%M:%SZ)"
