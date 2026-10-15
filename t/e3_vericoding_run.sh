#!/bin/bash
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PYT="$HOME/.venv-e3/bin/python"; LOG=out/E3-VERICODING.log
mkdir -p out/e3-vericoding
log(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }
log "VERICODING EVAL START (arms all7/graded/raw seed0, 14 non-recursion problems, k=5)"
for arm in all7 graded raw; do
  tag=$arm-s0; d=out/e3-vericoding/$tag
  if [ ! -f "$d/replies.jsonl" ]; then
    log "gen $tag"; $PYT -I gen_vericoding.py --model "out/e3-runs/$tag/merged" --tag "vc-$tag" \
      --limit 14 --samples 5 --max-new 768 --out "$d" >> "$LOG" 2>&1 && log "gen $tag OK" || log "gen $tag FAIL"
  fi
  if [ ! -f "$d/grade/verdicts.json" ] && [ -f "$d/replies.jsonl" ]; then
    log "grade $tag"; python3 -I grade.py --replies "$d/replies.jsonl" --out "$d/grade" --jobs 8 --flake 1 >> "$LOG" 2>&1
    log "grade $tag done (exit $?)"
  fi
done
$PYT -I e3_vericoding_aggregate.py 5 5 out/E3-VERICODING-RESULTS.json \
  all7:out/e3-vericoding/all7-s0/grade graded:out/e3-vericoding/graded-s0/grade raw:out/e3-vericoding/raw-s0/grade >> "$LOG" 2>&1
log "VERICODING EVAL COMPLETE"
