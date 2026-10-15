#!/bin/bash
# E3 full run: 3 arms x 3 seeds, matched budget. train_lora_cpu (CPU LoRA, merged) -> gen_eval_cpu
# (held-out MBPP, disjoint) -> grade.py (tests + 7 kernels). Resumable via existence checks. No AWS/GPU.
cd "$HOME/Projects/dawnr/t" || exit 1
export HF_HOME="$HOME/hf-cache" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
PYT="$HOME/.venv-e3/bin/python"          # torch venv: train + generate
LOG=out/E3-RUN.log
mkdir -p out/e3-runs out/e3-grade
log(){ echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG"; }
log "E3-RUN START (arms all7/graded/raw x seeds 0/1/2)"
for arm in all7 graded raw; do
  for seed in 0 1 2; do
    tag="$arm-s$seed"; run="out/e3-runs/$tag"
    if [ ! -d "$run/merged" ]; then
      log "train $tag"; $PYT -I train_lora_cpu.py --arm "out/e3-arms-matched/$arm.jsonl" --seed "$seed" \
        --out "$run" --epochs 5 >> "$LOG" 2>&1 && log "train $tag OK" || log "train $tag FAILED"
    fi
    if [ ! -d "out/spec-experiment/e3eval-$tag/raw" ] && [ -d "$run/merged" ]; then
      log "eval $tag"; $PYT -I gen_eval_cpu.py --model "$run/merged" --tag "e3eval-$tag" \
        --split out/loop/split-v6.json --limit 25 >> "$LOG" 2>&1 && log "eval $tag OK" || log "eval $tag FAILED"
    fi
    if [ ! -f "out/e3-grade/$tag/verdicts.json" ] && [ -d "out/spec-experiment/e3eval-$tag/raw" ]; then
      log "grade $tag"; python3 -I grade.py --replies "out/spec-experiment/e3eval-$tag/raw" \
        --out "out/e3-grade/$tag" --jobs 8 --flake 1 >> "$LOG" 2>&1 && log "grade $tag OK" || log "grade $tag FAILED"
    fi
    log "cell $tag done"
  done
done
log "E3-RUN COMPLETE"
