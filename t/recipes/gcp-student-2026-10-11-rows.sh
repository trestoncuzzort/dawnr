#!/usr/bin/env bash
# Reuse student_rows, graded_pool and the existing row audits.
# Prompt separation follows SAFE: https://arxiv.org/abs/2410.15756
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export T_SANDBOX=landlock CUDA_VISIBLE_DEVICES= PYTHONUNBUFFERED=1
OUT=t/out/gcp-student-2026-10-11-s1
PY="${PYTHON:-python3}"
test ! -e "$OUT/ROWS-AUDITED" || { echo "refusing to overwrite audited rows" >&2; exit 1; }
mkdir -p "$OUT"
"$PY" t/student_rows.py --corpus t/out/loop/corpus-r12-headed.txt --split t/out/loop/split-v5.json --split-seed 1338 \
  --train-rows t/out/loop/sft-r12-v5resolved.jsonl t/out/loop/sft-deepseek-{nine,b2,b3}.jsonl \
  --out "$OUT/spec-rows.jsonl" --heldout "$OUT/spec-heldout.jsonl"
"$PY" - <<'INNER'
import sys,json,hashlib,pathlib,collections
sys.path.insert(0,'t')
import spec_experiment as se, loop_filter, graded_pool, surface, loop_dataset
out=pathlib.Path('t/out/gcp-student-2026-10-11-s1')
paths=[out/'spec-rows.jsonl',pathlib.Path('t/out/loop/sft-r12-v5resolved.jsonl')]+[pathlib.Path('t/out/loop/sft-deepseek-'+n+'.jsonl') for n in ('nine','b2','b3')]
rows=[];manifest=[];seen=set();duplicates=0;blocked=[]
pool=se.pool("v7")
allowed=graded_pool.training_ids(pathlib.Path("t/out/loop/split-v5.json"),pool)
for p in paths:
 r=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
 manifest.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':len(r)})
 for row in r:
  if 'task_id' in row:
   tid=int(row['task_id'])
   if tid not in allowed:
    blocked.append({'path':str(p),'task_id':tid})
    continue
   task=surface.parse(se.find_block(row['chosen']))
   row={**row,'name':row.get('name',row.get('task',task['name'])), 'prompt':se.build_prompt(pool[tid],'s1'), 'chosen':loop_dataset.fence(graded_pool.answer_text(task,pool[tid]['fn'])), 'prompt_version':'s1'}
  key=json.dumps([row['prompt'],row['chosen']],sort_keys=True)
  if key in seen: duplicates+=1;continue
  rows.append(row);seen.add(key)
pool=se.pool('v7')
split=json.loads(pathlib.Path('t/out/loop/split-v5.json').read_text())
required=set(split['eval_ids'])|set(loop_filter.r12_dev_ids(pathlib.Path('t/r12-dev-ids.json')))
missing=sorted(required-set(pool))
if missing: raise SystemExit('Missing held-out/dev reference problems: '+str(missing))
(out/'raw-rows.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
record={'sources':manifest,'raw_rows':len(rows),'blocked_by_current_split':blocked,'exact_duplicates_removed':duplicates,'pool_size':len(pool),'required_eval_dev':len(required),'missing_eval_dev':missing}
(out/'build-inputs.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
INNER
"$PY" t/heldout_audit.py --rows "$OUT/raw-rows.jsonl" --panels --refuse-gpl --jobs 4 --json "$OUT/audit-raw.json" --keep "$OUT/lineage-clean.jsonl" > "$OUT/audit-raw.log" 2>&1 || test "$?" -eq 1
"$PY" t/spec_panel.py check --rows "$OUT/lineage-clean.jsonl" --panel "$OUT/spec-heldout.jsonl" --keep "$OUT/train-rows.jsonl" --json "$OUT/spec-audit.json" > "$OUT/spec-audit.log" 2>&1 || test "$?" -eq 1
"$PY" t/heldout_audit.py --rows "$OUT/train-rows.jsonl" --panels --refuse-gpl --jobs 4 --json "$OUT/audit-final.json" > "$OUT/audit-final.log" 2>&1
"$PY" t/spec_panel.py check --rows "$OUT/train-rows.jsonl" --panel "$OUT/spec-heldout.jsonl" --json "$OUT/spec-audit-final.json" > "$OUT/spec-audit-final.log" 2>&1
sha256sum "$OUT/train-rows.jsonl" "$OUT/spec-heldout.jsonl"
wc -l "$OUT/train-rows.jsonl"
touch "$OUT/ROWS-AUDITED"
