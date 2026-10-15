#!/bin/bash
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache"
PYT="$HOME/.venv-e3/bin/python"; LOG=out/E3-BASE15.log; B=Qwen/Qwen2.5-Coder-1.5B-Instruct
log(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }
log "BASE15 START (download + train all7-s0 on 1.5B, eval held-out MBPP)"
log "download $B"; $PYT -c "from huggingface_hub import snapshot_download; snapshot_download('$B')" >> "$LOG" 2>&1 && log "download OK" || { log "download FAIL"; exit 1; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
if [ ! -d out/e3-base15/all7-s0/merged ]; then
  log "train 1.5B all7-s0"; $PYT -I train_lora_cpu.py --base "$B" --rev main --arm out/e3-arms-matched/all7.jsonl \
    --seed 0 --out out/e3-base15/all7-s0 --epochs 5 >> "$LOG" 2>&1 && log "train OK" || log "train FAIL"
fi
if [ ! -d out/spec-experiment/e3b15-all7-s0/raw ] && [ -d out/e3-base15/all7-s0/merged ]; then
  log "eval 1.5B all7-s0"; $PYT -I gen_eval_cpu.py --model out/e3-base15/all7-s0/merged --tag e3b15-all7-s0 \
    --split out/loop/split-v6.json --limit 25 >> "$LOG" 2>&1 && log "eval OK" || log "eval FAIL"
fi
if [ ! -f out/e3-base15-grade/all7-s0/verdicts.json ] && [ -d out/spec-experiment/e3b15-all7-s0/raw ]; then
  log "grade 1.5B all7-s0"; python3 -I grade.py --replies out/spec-experiment/e3b15-all7-s0/raw \
    --out out/e3-base15-grade/all7-s0 --jobs 8 --flake 1 >> "$LOG" 2>&1; log "grade done (exit $?)"
fi
log "BASE15 COMPLETE"
