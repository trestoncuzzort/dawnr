#!/bin/bash
# E3 full run: 3 arms x 3 seeds, each train (merged) -> eval (held-out MBPP) -> grade (tests + 7 kernels).
# Resumable: every step is skipped if its output already exists. Uses the prompt-consistent existing tools.
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PY="$HOME/.venv-e3/bin/python"
R=out/e3-runs; mkdir -p "$R"
SPLIT=out/loop/split-v6.json; LIMIT=40
log(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$R/drive.log"; }
declare -A ARM=( [all7]=out/e3-arms-matched/all7.jsonl [graded]=out/e3-arms-matched/graded.jsonl [raw]=out/e3-arms-matched/raw.jsonl )
log "E3-DRIVE-START"
for a in all7 graded raw; do
  for s in 0 1 2; do
    tag="$a-s$s"; o="$R/$tag"
    if [ ! -d "$o/merged" ]; then log "train $tag"; $PY -I train_lora_cpu.py --arm "${ARM[$a]}" --seed "$s" --out "$o" >> "$R/$tag.log" 2>&1 || log "TRAIN-FAIL $tag"; fi
    if [ ! -d "out/spec-experiment/e3eval-$tag/raw" ]; then log "eval $tag"; $PY -I gen_eval_cpu.py --model "$o/merged" --tag "e3eval-$tag" --split "$SPLIT" --limit "$LIMIT" >> "$R/$tag.log" 2>&1 || log "EVAL-FAIL $tag"; fi
    if [ ! -f "$o/grade/summary.txt" ]; then log "grade $tag"; $PY -I grade.py --replies "out/spec-experiment/e3eval-$tag/raw" --out "$o/grade" --jobs 8 --flake 1 >> "$R/$tag.log" 2>&1 || log "GRADE-FAIL $tag"; fi
    log "done $tag"
  done
done
log "E3-DRIVE-ALL-DONE"
