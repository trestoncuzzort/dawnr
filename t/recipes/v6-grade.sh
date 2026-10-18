#!/usr/bin/env bash
# Existing seven-kernel, specification, completeness and larger-input gates.
# Prior recipe: v5-matched-2026-10-11-grade.sh.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
tag="${1:?generation tag}"
ids="${2:?frozen problem panel}"
out="${3:?fresh output directory}"
export T_MIN_KERNELS=7 T_SPARK_JOBS=1 T_SANDBOX=landlock PYTHONUNBUFFERED=1
mkdir -p "$out"
exec 9>"$out/grade.lock"
flock -n 9
test ! -e "$out/GRADED"
python3 t/spec_experiment.py extract --model "$tag" --pool v5 --promote-header
python3 t/spec_experiment.py tests --model "$tag" --pool v5
table="t/out/spec-experiment/$tag/kernels.md"
tasks="t/out/spec-experiment/$tag/tasks"
test ! -e "$table"
python3 - "$out" "$ids" <<'PY'
import hashlib, json, pathlib, sys
out, panel = map(pathlib.Path, sys.argv[1:])
files = sorted(pathlib.Path('t').glob('*.py')) + sorted(pathlib.Path('t/verifiers').rglob('*.py'))
files += [pathlib.Path('t/recipes/v6-grade.sh'), pathlib.Path('t/recipes/bounded-grading-python.py'), panel]
record = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out/'evaluator.json').write_text(json.dumps(record, indent=2)+'\n')
PY
status=0
python3 t/recipes/bounded-grading-python.py t/run_par.py --tasks "$tasks" \
  --out "$out/kernels" --table "$table" --jobs 1 --no-cache > "$out/kernels.log" 2>&1 || status=$?
test "$status" -le 1 && test -s "$table"
python3 - "$table" "$tasks" <<'PY'
import json, pathlib, sys
sys.path.insert(0, 't')
import spec_experiment as se, spec_check
columns, rows = se.parse_kernel_table(pathlib.Path(sys.argv[1]))
names = {json.loads(p.read_text())['name'] for p in pathlib.Path(sys.argv[2]).glob('*.json')}
assert names and set(columns) == set(spec_check.KERNELS), 'incomplete kernel coverage'
assert set(rows) == names, 'incomplete task coverage'
PY
# spec_check keeps a shared verdict index; serialize writes and capture this tag.
exec 8>t/out/v6-20261018/spec-check.lock
flock -x 8
python3 t/spec_check.py "$tag" --pool v5 --only all --n 1000 --per-task-seed \
  --reference-plus t/out/gcp-student-2026-10-11-s1/reference/mbppplus.jsonl --out "$out/spec-check.md"
python3 - "$tag" "$out" "$tasks" <<'PY'
import json, pathlib, sys
tag, output, tasks = sys.argv[1:]
all_results = json.loads(pathlib.Path('t/out/spec-disagree.json').read_text())['results']
results = {k:v for k,v in all_results.items() if k.startswith(tag+'/')}
names = {json.loads(p.read_text())['name'] for p in pathlib.Path(tasks).glob('*.json')}
assert set(results) == {tag+'/'+name for name in names}, 'incomplete specification checks'
pathlib.Path(output, 'verdicts.json').write_text(json.dumps({'tags':[tag], 'results':results}, indent=2)+'\n')
PY
flock -u 8
python3 t/score_levels.py "$tag" --ids-file "$ids" --verdicts "$out/verdicts.json" \
  --min-completeness 0.6 --larger --json "$out/levels.json"
touch "$out/GRADED"
