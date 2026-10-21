#!/bin/bash
# Resume the v8 training on the LAPTOP's GPU (RTX 5050 Laptop, 8 GB) from the checkpoints the Modal H100 run saved (steps 400
# and 500 of 1,550; the user stopped the paid run on 2026-10-21). student_sft.py resumes when trainer/checkpoint-* exists under
# --out and the data fingerprints match (trainer.train(resume_from_checkpoint=True)); --small-card is the chunked loss that
# fits 8 GB (the loss is the same quantity). Same arguments as t/recipes/v7_modal.py and v8_desktop_train.sh. The torch
# build differs (laptop 2.11.0+cu128, Modal 2.9.1+cu129): recorded in t/PREDICT-2026-10-21-v8-spec-rows.md.
set -u
D=/home/t/Projects/dawnr; V=$D/t/out/v8-20261021; VENV=/home/t/scratch/venv-train
ROWS=$V/v8-rows.jsonl; ROWS_SHA=a279cc9a1b878865a447c61a67fc14250c39869c915e0cf7d3932ba6faf2cd03
SNAP=$(ls -d /home/t/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a)
cd $D || exit 1
rm -f $V/train.done
echo "$(date -u +%FT%TZ) resume on the laptop from $(ls $V/adapter/trainer | tail -1) rows=$ROWS sha=$ROWS_SHA" >> $V/train.log
export HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1 PYTORCH_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=6
$VENV/bin/python $D/t/student_sft.py --model "$SNAP" --sft $ROWS --sft-sha256 $ROWS_SHA --out $V/adapter \
  --rank 64 --alpha 16 --dropout 0.1 --lr 2e-4 --epochs 5 --max-len 2845 --seed 1 --batch 1 --grad-accum 16 \
  --save-steps 100 --log-every 10 --small-card >> $V/train.log 2>&1
RC=$?
echo "$(date -u +%FT%TZ) rc=$RC" >> $V/train.log
echo $RC > $V/train.done
