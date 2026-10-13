#!/usr/bin/env bash
# VM side: the registered sequence of t/PREDICT-2026-10-13-udebug-student.md. Every stage leaves a marker so a
# restart resumes. A: the base answers the 377 held-out judge questions; B: the 10-11 adapter merged, answers;
# train on the frozen rows; C: this run's adapter merged, answers + the 33 specification questions; export Q8_0.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 HF_HUB_DISABLE_TELEMETRY=1
OUT=t/out/udebug-student-2026-10-13
PY=t/out/gcp-venv/bin/python
test -f "$OUT/SETUP-DONE"
printf '%s  %s\n' 1bebb99c69e1b58863c39507d7ce5b7d9f617918e1c21a2f1d063f436740b2fb "$OUT/train-rows.jsonl" | sha256sum -c -
printf '%s  %s\n' 8704ca97d1a3c64997f2dac5ab7199415b442f80eef9382e156e41a510b60ede "$OUT/judge-heldout.jsonl" | sha256sum -c -
stage() { test -f "$OUT/$1"; }
# A: the base
if ! stage A-DONE; then
  "$PY" t/udebug_student.py --questions "$OUT/judge-heldout.jsonl" --tag base-q35-4b --backend hf \
    --model t/out/gcp-base --max-new 1024 --batch 8 --out "$OUT/answers-A-base"
  touch "$OUT/A-DONE"
fi
# B: the 10-11 student (control)
if ! stage B-DONE; then
  test -f "$OUT/adapter-1011/adapter_model.safetensors"
  "$PY" t/student_sft.py --merge "$OUT/adapter-1011" --out "$OUT/merged-1011"
  "$PY" t/udebug_student.py --questions "$OUT/judge-heldout.jsonl" --tag student-1011 --backend hf \
    --model "$OUT/merged-1011" --max-new 1024 --batch 8 --out "$OUT/answers-B-student-1011"
  rm -rf "$OUT/merged-1011"
  touch "$OUT/B-DONE"
fi
# train
if ! stage TRAINED; then
  "$PY" - <<'PY'
import collections, json, pathlib, sys
sys.path.insert(0, 't')
import student_sft
from transformers import AutoTokenizer
out = pathlib.Path('t/out/udebug-student-2026-10-13')
tokenizer = AutoTokenizer.from_pretrained('t/out/gcp-base')
rows = student_sft.load_rows(out/'train-rows.jsonl')
used, dropped = [], []
for index, row in enumerate(rows):
    encoded = student_sft.encode_row(tokenizer, row, 2845)
    entry = {'index': index, 'kind': row.get('kind', 'sft'), 'name': row.get('name'), 'problem': row.get('problem')}
    (used if encoded else dropped).append(entry)
record = {'rows': len(rows), 'used': len(used), 'used_by_kind': dict(collections.Counter(r['kind'] for r in used)),
          'dropped': dropped, 'base_revision': '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'}
(out/'tokenization.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k: v for k, v in record.items() if k != 'dropped'}, indent=None), flush=True)
PY
  "$PY" t/student_sft.py --model t/out/gcp-base --sft "$OUT/train-rows.jsonl" \
    --out "$OUT/adapter" --epochs 5 --lr 2e-4 --rank 64 --alpha 16 --dropout 0.1 \
    --batch 1 --grad-accum 16 --max-len 2845 --seed 1 --save-steps 50 --log-every 5
  test -s "$OUT/adapter/run.json"
  touch "$OUT/TRAINED"
fi
# C: this run's student
if ! stage C-DONE; then
  test -d "$OUT/merged" || "$PY" t/student_sft.py --merge "$OUT/adapter" --out "$OUT/merged"
  "$PY" t/udebug_student.py --questions "$OUT/judge-heldout.jsonl" --tag student-1013 --backend hf \
    --model "$OUT/merged" --max-new 1024 --batch 8 --out "$OUT/answers-C-student-1013"
  "$PY" t/score_spec_given.py ask --model "$OUT/merged" --questions "$OUT/spec-heldout.jsonl" \
    --out "$OUT/spec-answers.jsonl" --system s1 --max-new 1024
  touch "$OUT/C-DONE"
fi
# export Q8_0 with the pinned converter
if ! stage EXPORTED; then
  mkdir -p "$OUT/export"
  CUDA_VISIBLE_DEVICES= "$PY" t/out/llama.cpp/convert_hf_to_gguf.py "$OUT/merged" \
    --outfile "$OUT/export/dawnr-udebug-20261013-Q8_0.gguf" --outtype q8_0 --no-mtp \
    --model-name "dawnr 2026-10-13 judge-row candidate"
  sha256sum "$OUT/export/dawnr-udebug-20261013-Q8_0.gguf" "$OUT/adapter/adapter_model.safetensors" > "$OUT/SHA256SUMS"
  touch "$OUT/EXPORTED"
fi
echo RUN-DONE
