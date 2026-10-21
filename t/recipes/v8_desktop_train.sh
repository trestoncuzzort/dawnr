#!/bin/bash
# v8 training on the desktop GPU node (tlab, RTX 4080 16 GB): the exact v5 recipe as run for v7 on Modal
# (t/recipes/v7_modal.py: rank 64, alpha 16, dropout 0.1, lr 2e-4, 5 epochs, max-len 2845, seed 1, batch 1, grad-accum 16),
# the pinned trainer t/student_sft.py (sha e43c27df…), the pinned base Qwen/Qwen3.5-4B@851bf6e8 from ~/hf-cache, inside
# ~/venv-train (torch 2.9.1 cu129, transformers 5.20.1, peft 0.21.2, bitsandbytes 0.50.2). Launch as a user unit.
#   ROWS=/home/t/v8/v8-rows.jsonl ROWS_SHA=<sha256> bash t/recipes/v8_desktop_train.sh
# SMALL_CARD=1 adds --small-card (the chunked loss) if the card runs out of memory; the loss is the same quantity.
set -u
H=/home/t; D=$H/dawnr; V=$H/v8; VENV=$H/venv-train
ROWS=${ROWS:-$V/v8-rows.jsonl}; ROWS_SHA=${ROWS_SHA:?sha256 of the rows}
SNAP=$(cat $H/venv-train.snapshot)
TRAINER_SHA=e43c27df1ee1e796b1799d38a16e0c5725dd09df762be3fabb2940ad8cb4a46f
mkdir -p $V; cd $D || exit 1
rm -f $V/train.done
echo "$(date -u +%FT%TZ) start rows=$ROWS sha=$ROWS_SHA snapshot=$SNAP" > $V/train.log
[ "$(sha256sum $D/t/student_sft.py | cut -c1-64)" = "$TRAINER_SHA" ] || { echo "trainer sha differs" >> $V/train.log; echo 92 > $V/train.done; exit 1; }
EXTRA=""; [ "${SMALL_CARD:-0}" = 1 ] && EXTRA="--small-card"
export HF_HUB_OFFLINE=1 HF_HUB_CACHE=$H/hf-cache PYTHONUNBUFFERED=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=8
$VENV/bin/python $D/t/student_sft.py --model "$SNAP" --sft $ROWS --sft-sha256 $ROWS_SHA --out $V/adapter \
  --rank 64 --alpha 16 --dropout 0.1 --lr 2e-4 --epochs 5 --max-len 2845 --seed 1 --batch 1 --grad-accum 16 \
  --save-steps 100 --log-every 10 $EXTRA >> $V/train.log 2>&1
RC=$?
echo "$(date -u +%FT%TZ) rc=$RC" >> $V/train.log
echo $RC > $V/train.done
