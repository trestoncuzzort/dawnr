#!/usr/bin/env bash
# Fixed-recipe QLoRA: https://arxiv.org/abs/2305.14314
# Run only on the capped GPU VM, after the row audits have passed.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
export HF_HUB_DISABLE_TELEMETRY=1
OUT=t/out/gcp-student-2026-10-11-s1
PY=t/out/gcp-venv/bin/python
test -f "$OUT/ROWS-AUDITED"
printf '%s  %s\n' 0248cf93e57092d91d0f8b6471a22ffae0a5f7aeff337f24bc8604155094fb39 "$OUT/train-rows.jsonl" | sha256sum -c -
printf '%s  %s\n' effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24 "$OUT/spec-heldout.jsonl" | sha256sum -c -
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "$OUT/gpu.csv"
"$PY" -m pip freeze > "$OUT/environment.txt"
"$PY" - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3.5-4B', revision='851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a',
                  local_dir='t/out/gcp-base', allow_patterns=['*.json', '*.safetensors', '*.jinja', '*.txt', 'LICENSE*'])
PY
"$PY" - <<'PY'
import collections, hashlib, json, pathlib, sys
sys.path.insert(0, 't')
import student_sft
from transformers import AutoTokenizer
out = pathlib.Path('t/out/gcp-student-2026-10-11-s1')
tokenizer = AutoTokenizer.from_pretrained('t/out/gcp-base')
rows = student_sft.load_rows(out/'train-rows.jsonl')
used, dropped = [], []
for index, row in enumerate(rows):
    encoded = student_sft.encode_row(tokenizer, row, 2845)
    entry = {'index': index, 'kind': row.get('kind', 'sft'), 'task_id': row.get('task_id'), 'name': row.get('name')}
    (used if encoded else dropped).append(entry)
record = {'rows': len(rows), 'used': len(used), 'used_by_kind': dict(collections.Counter(r['kind'] for r in used)),
          'dropped': dropped, 'base_revision': '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'}
(out/'tokenization.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record), flush=True)
if not any(r['kind'] == 'sft' for r in used):
    raise SystemExit('No English training row fits the registered token limit')
PY
"$PY" t/student_sft.py --model t/out/gcp-base --sft "$OUT/train-rows.jsonl" \
  --out "$OUT/adapter" --epochs 5 --lr 2e-4 --rank 64 --alpha 16 --dropout 0.1 \
  --batch 1 --grad-accum 16 --max-len 2845 --seed 1 --save-steps 25 --log-every 1
test -s "$OUT/adapter/run.json"
touch "$OUT/TRAINED"
"$PY" t/student_sft.py --merge "$OUT/adapter" --out "$OUT/merged"
"$PY" t/score_spec_given.py ask --model "$OUT/merged" --questions "$OUT/spec-heldout.jsonl" \
  --out "$OUT/spec-answers.jsonl" --system s1 --max-new 1024
"$PY" - <<'PY'
import json, pathlib
p = pathlib.Path('t/out/gcp-student-2026-10-11-s1/eval-ids.txt')
ids = json.loads(pathlib.Path('t/out/loop/split-v5.json').read_text())['eval_ids']
assert len(set(ids)) == 232
p.write_text(''.join(str(i)+'\n' for i in ids))
PY
"$PY" t/student_generate.py --model "$OUT/merged" --tag gcp-student-20261011-greedy \
  --pool v5 --prompt s1 --ids-file "$OUT/eval-ids.txt" --temperature 0 --max-new 1024 --batch 4
"$PY" - <<'PY'
import json, pathlib
out = pathlib.Path('t/out/gcp-student-2026-10-11-s1')
questions = [json.loads(l)['name'] for l in (out/'spec-heldout.jsonl').read_text().splitlines()]
answers = [json.loads(l)['name'] for l in (out/'spec-answers.jsonl').read_text().splitlines()]
assert len(answers) == len(questions) and set(answers) == set(questions)
ids = {str(i) for i in json.loads(pathlib.Path('t/out/loop/split-v5.json').read_text())['eval_ids']}
files = list(pathlib.Path('t/out/spec-experiment/gcp-student-20261011-greedy/raw').glob('*.json'))
assert {p.stem for p in files} == ids
for path in files:
    json.loads(path.read_text())
(out/'GENERATED').touch()
PY
