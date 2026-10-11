#!/usr/bin/env bash
# The registered single-answer reading, through the existing seven-kernel and
# larger-input gates. EvalPlus references: https://arxiv.org/abs/2305.01210
# Run on the lab CPU after copying the generated records from the GPU VM.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export T_SANDBOX=landlock CUDA_VISIBLE_DEVICES= PYTHONUNBUFFERED=1 T_SPARK_JOBS=1
OUT=t/out/gcp-student-2026-10-11-s1
TAG=gcp-student-20261011-greedy
PY="${PYTHON:-python3}"
test -f "$OUT/GENERATED"
# run_par exits 1 for a measured disagreement, and 2 for a refused run.
# Require a newly written table so an exception cannot reuse stale evidence.
grade() {
  local table="$1" tasks="$2" output="$3" status=0
  test ! -e "$table" || { echo "existing table: $table" >&2; return 2; }
  "$PY" t/run_par.py --table "$table" --tasks "$tasks" --out "$output" --jobs 4 --no-cache || status=$?
  test "$status" -le 1 && test -s "$table"
  "$PY" - "$table" "$tasks" <<'PY'
import json, pathlib, sys
sys.path.insert(0, 't')
import spec_experiment, spec_check
columns, rows = spec_experiment.parse_kernel_table(pathlib.Path(sys.argv[1]))
names = {json.loads(p.read_text())['name'] for p in pathlib.Path(sys.argv[2]).glob('*.json')}
assert names and set(columns) == set(spec_check.KERNELS), 'missing tasks or kernel columns'
assert set(rows) == names, 'partial or foreign matrix rows'
PY
}
"$PY" - <<'PY'
import hashlib, json, pathlib, subprocess
root = pathlib.Path('.')
out = root/'t/out/gcp-student-2026-10-11-s1'
split = json.loads((root/'t/out/loop/split-v5.json').read_text())
raw = root/'t/out/spec-experiment/gcp-student-20261011-greedy/raw'
assert {p.stem for p in raw.glob('*.json')} == {str(i) for i in split['eval_ids']}
files = list((root/'t').glob('*.py')) + list((root/'t/verifiers').rglob('*.py'))
manifest = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'files': {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
(out/'evaluator.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
"$PY" t/score_spec_given.py prepare --questions "$OUT/spec-heldout.jsonl" \
  --answers "$OUT/spec-answers.jsonl" --tasks "$OUT/spec-tasks" --report "$OUT/spec-report.json"
grade "$OUT/spec-kernels.md" "$OUT/spec-tasks" "$OUT/spec-kernels" > "$OUT/spec-kernels.log" 2>&1
"$PY" t/score_spec_given.py levels --report "$OUT/spec-report.json" --table "$OUT/spec-kernels.md" \
  --json "$OUT/spec-levels.json"
"$PY" t/spec_experiment.py extract --model "$TAG" --pool v5 --promote-header
"$PY" t/spec_experiment.py tests --model "$TAG" --pool v5
grade "t/out/spec-experiment/$TAG/kernels.md" "t/out/spec-experiment/$TAG/tasks" \
  "$OUT/problem-kernels" > "$OUT/problem-kernels.log" 2>&1
"$PY" t/spec_check.py "$TAG" --pool v5 --only all --n 1000 --per-task-seed \
  --reference-plus "$OUT/reference/mbppplus.jsonl" --out "$OUT/spec-check.md"
"$PY" - <<'PY'
import json, pathlib
out = pathlib.Path('t/out/gcp-student-2026-10-11-s1')
all_verdicts = json.loads(pathlib.Path('t/out/spec-disagree.json').read_text())
tag = 'gcp-student-20261011-greedy'
record = {'tags': [tag], 'results': {k:v for k,v in all_verdicts.get('results',{}).items() if k.startswith(tag+'/')}}
(out/'verdicts.json').write_text(json.dumps(record,indent=2)+'\n')
PY
"$PY" t/score_levels.py "$TAG" --split t/out/loop/split-v5.json --panel clean-182 \
  --verdicts "$OUT/verdicts.json" --min-completeness 0.6 --larger --json "$OUT/problem-levels.json"
touch "$OUT/GRADED"
