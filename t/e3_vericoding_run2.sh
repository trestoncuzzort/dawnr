#!/bin/bash
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PYT="$HOME/.venv-e3/bin/python"; LOG=out/E3-VERICODING2.log
mkdir -p out/e3-vericoding2
log(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }
log "VERICODING2 START (3 arms x 3 seeds, 20 problems, k=5, deterministic ids)"
for arm in all7 graded raw; do
  for seed in 0 1 2; do
    tag=$arm-s$seed; d=out/e3-vericoding2/$tag
    if [ ! -f "$d/replies.jsonl" ]; then
      log "gen $tag"; $PYT -I gen_vericoding.py --model "out/e3-runs/$tag/merged" --tag "vc2-$tag" \
        --limit 20 --samples 5 --max-new 768 --out "$d" >> "$LOG" 2>&1 && log "gen $tag OK" || log "gen $tag FAIL"
    fi
    if [ ! -f "$d/grade/verdicts.json" ] && [ -f "$d/replies.jsonl" ]; then
      log "grade $tag"; python3 -I grade.py --replies "$d/replies.jsonl" --out "$d/grade" --jobs 8 --flake 1 >> "$LOG" 2>&1
      log "grade $tag done (exit $?)"
    fi
  done
done
$PYT -I e3_vericoding_aggregate.py 5 5 20 out/E3-VERICODING2-RESULTS.json \
  all7:out/e3-vericoding2/all7-s0/grade,out/e3-vericoding2/all7-s1/grade,out/e3-vericoding2/all7-s2/grade \
  graded:out/e3-vericoding2/graded-s0/grade,out/e3-vericoding2/graded-s1/grade,out/e3-vericoding2/graded-s2/grade \
  raw:out/e3-vericoding2/raw-s0/grade,out/e3-vericoding2/raw-s1/grade,out/e3-vericoding2/raw-s2/grade >> "$LOG" 2>&1
log "VERICODING2 COMPLETE"
