#!/bin/bash
# Grade the prover's unscored answers and rebuild the training pool with them.
# This is the only lever measured to move locallm's absolute score.
#
#   bash t/grow_pool.sh prover-train2
#
# prover-train2 has 450 of 2,354 training problems answered and never graded.
# Its predecessor prover-train converted 31 of 88 graded cells into clean
# answers. Resume generation first if you want more: /tmp/gen_prover2.sh on the
# lab, which skips every problem that already has a record.
set -u
cd "$(dirname "$0")/.."
TAG=${1:-prover-train2}
[ -f t/lab-workstation.conf ] && . t/lab-workstation.conf

echo "== extract and tests: $TAG =="
python3 t/spec_experiment.py extract --model "$TAG" --pool v5 || exit 1
python3 t/spec_experiment.py tests   --model "$TAG" --pool v5 || exit 1

echo "== all seven kernels =="
bash t/grade_lab.sh heldout "$TAG" || exit 1

echo "== the check the gate refuses answers for =="
# Without this every clean answer is rejected as spec-unchecked. That is what
# was holding 246 answers out of the pool on 2026-09-19.
python3 t/spec_check.py "$TAG" --pool v5 --n 100 --only clean \
  --out "$PWD/t/SPEC-CHECK-$TAG.md" || exit 1

echo "== rebuild the pool =="
TAGS=$(cd t/out/spec-experiment && ls -d qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 qwen3.8-27b-fp8-v3-s2 \
  qwen2.5-coder-14b-* qwen3-coder-30b-* deepseek-coder-v2-16b-* 2>/dev/null)
python3 t/loop_dataset.py --from-samples $TAGS student-r4-train locallm-r4-train \
  prover-train "$TAG" --split t/out/loop/split-v5.json --min-kernels 7 --out-suffix r10 || exit 1
wc -l t/out/loop/sft-r10.jsonl t/out/loop/pairs-r10.jsonl

echo
echo "Then train on it, headed and greedy, which is the recipe that tied Phi:"
echo "  python3 t/loop_locallm.py corpus --pool v5 --lifted --sft t/out/loop/sft-r10.jsonl \\"
echo "      --out t/out/loop/corpus-r10.txt"
echo "  python3 t/head_align_corpus.py --corpus t/out/loop/corpus-r10.txt \\"
echo "      --out t/out/loop/corpus-r10-headed.txt"
echo "  ~/.venv-vllm/bin/python locallm/continue_from_checkpoint.py \\"
echo "      --init t/out/source-pretraining-longer-2026-09-19/gpt-seed1337 \\"
echo "      --data t/out/loop/corpus-r10-headed.txt --split t/out/loop/split-v5.json --out t/out/locallm-r10 --steps 300 --lr 3e-5"
echo "  python3 t/loop_locallm.py generate --temperature 0 --model t/out/locallm-r10 --tag locallm-r10 \\"
echo "      --split t/out/loop/split-v5.json --tokens 1200 --temperature 0"
