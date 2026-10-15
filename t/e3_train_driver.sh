#!/bin/bash
cd ~/Projects/dawnr/t
export HF_HOME="$HOME/hf-cache" E3_THREADS=40
printf '%s\n' "raw 0" "raw 1" "raw 2" "graded 0" "graded 1" "graded 2" "all7 0" "all7 1" "all7 2" \
 | xargs -P 3 -L 1 bash -c '
     ~/e3-venv/bin/python train_lora_cpu.py --base Qwen/Qwen2.5-Coder-0.5B-Instruct \
       --arm "out/e3-arms/$1.jsonl" --seed "$2" --out "out/e3-runs/$1-s$2" --epochs 3 \
       > "out/e3-runs/$1-s$2.log" 2>&1
     echo "[$(date -u +%H:%M:%SZ)] DONE $1-s$2"
   ' _
echo "E3-ALL-TRAINING-DONE $(date -u +%H:%M:%SZ)"
