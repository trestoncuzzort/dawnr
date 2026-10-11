#!/usr/bin/env bash
# The registered single-answer reading, through the existing seven-kernel and
# larger-input gates. EvalPlus references: https://arxiv.org/abs/2305.01210
# Both matched Q8 arms use the same lab evaluator and gates.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export T_SANDBOX=landlock CUDA_VISIBLE_DEVICES= PYTHONUNBUFFERED=1 T_SPARK_JOBS=1
ARM="${1:?give v5 or recovered}"
case "$ARM" in v5|recovered) ;; *) exit 2 ;; esac
OUT="t/out/v5-matched-20261011/$ARM"
TAG="v5-matched-20261011-$ARM"
export MATCH_OUT="$OUT" MATCH_TAG="$TAG"
mkdir -p "$OUT"
if [ ! -e "$OUT/spec-heldout.jsonl" ]; then
  cp t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl "$OUT/spec-heldout.jsonl"
fi
cmp t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl "$OUT/spec-heldout.jsonl"
PY="${PYTHON:-python3}"
PHASE="${2:-all}"
case "$PHASE" in spec) ;; all) test -f "$OUT/GENERATED" ;; *) exit 2 ;; esac
exec 9>"$OUT/grade.lock"
flock -x 9
# run_par exits 1 for a measured disagreement, and 2 for a refused run.
# Require a newly written table so an exception cannot reuse stale evidence.
grade() {
  local table="$1" tasks="$2" output="$3" status=0
  test ! -e "$table" || { echo "existing table: $table" >&2; return 2; }
  "$PY" t/run_par.py --table "$table" --tasks "$tasks" --out "$output" --jobs 2 --no-cache || status=$?
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
"$PY" - "$PHASE" <<'PY'
import hashlib, json, os, pathlib, subprocess, sys
sys.path.insert(0, 't')
import score_heldout
root = pathlib.Path('.')
out = root/os.environ['MATCH_OUT']
questions = [json.loads(l)['name'] for l in (out/'spec-heldout.jsonl').read_text().splitlines()]
answers = [json.loads(l)['name'] for l in (out/'spec-answers.jsonl').read_text().splitlines()]
assert len(answers) == len(questions) == 33 and set(answers) == set(questions)
if sys.argv[1] == 'all':
    split = json.loads((root/'t/out/loop/split-v5.json').read_text())
    raw = root/'t/out/spec-experiment'/os.environ['MATCH_TAG']/'raw'
    ids = set((root/'t/out/v5-matched-20261011/clean-200.txt').read_text().split())
    expected = {str(i) for i in score_heldout.clean_eval_ids(set(split['eval_ids']))}
    assert ids == expected and len(ids) == 200 and {p.stem for p in raw.glob('*.json')} == ids
files = list((root/'t').glob('*.py')) + list((root/'t/verifiers').rglob('*.py'))
manifest = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'files': {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
if (out/'evaluator.json').exists():
    assert json.loads((out/'evaluator.json').read_text()) == manifest, 'evaluator changed between panels'
(out/'evaluator.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
# Whole-stage reuse follows dawnr_pipeline's input fingerprints and DVC's run
# cache (https://doc.dvc.org/user-guide/pipelines/run-cache). Every kernel is
# actually invoked on the first pass; completed evidence must still match.
spec_receipt() {
  "$PY" - "$1" <<'PY'
import hashlib, json, os, pathlib, sys
out = pathlib.Path(os.environ['MATCH_OUT'])
names = ['spec-heldout.jsonl','spec-answers.jsonl','evaluator.json','spec-report.json','spec-kernels.md','spec-levels.json']
record = {n: hashlib.sha256((out/n).read_bytes()).hexdigest() for n in names}
record['grading_script_sha256'] = hashlib.sha256(pathlib.Path('t/recipes/v5-matched-2026-10-11-grade.sh').read_bytes()).hexdigest()
receipt = out/'spec-stage.json'
if sys.argv[1] == 'check':
    assert json.loads(receipt.read_text()) == record, 'specification-stage evidence changed'
else:
    receipt.write_text(json.dumps(record,indent=2)+'\n')
PY
}
if [ -f "$OUT/spec-stage.json" ]; then
  spec_receipt check
  echo 'specification panel already graded; input, evaluator and output hashes match'
else
"$PY" t/score_spec_given.py prepare --questions "$OUT/spec-heldout.jsonl" \
  --answers "$OUT/spec-answers.jsonl" --tasks "$OUT/spec-tasks" --report "$OUT/spec-report.json"
grade "$OUT/spec-kernels.md" "$OUT/spec-tasks" "$OUT/spec-kernels" > "$OUT/spec-kernels.log" 2>&1
"$PY" t/score_spec_given.py levels --report "$OUT/spec-report.json" --table "$OUT/spec-kernels.md" \
  --json "$OUT/spec-levels.json"
  spec_receipt write
fi
if [ "$PHASE" = spec ]; then exit 0; fi
"$PY" t/spec_experiment.py extract --model "$TAG" --pool v5 --promote-header
"$PY" t/spec_experiment.py tests --model "$TAG" --pool v5
grade "t/out/spec-experiment/$TAG/kernels.md" "t/out/spec-experiment/$TAG/tasks" \
  "$OUT/problem-kernels" > "$OUT/problem-kernels.log" 2>&1
exec 8>t/out/v5-matched-20261011/spec-check.lock
flock -x 8
"$PY" t/spec_check.py "$TAG" --pool v5 --only all --n 1000 --per-task-seed \
  --reference-plus t/out/gcp-student-2026-10-11-s1/reference/mbppplus.jsonl --out "$OUT/spec-check.md"
"$PY" - <<'PY'
import json, os, pathlib
out = pathlib.Path(os.environ['MATCH_OUT'])
all_verdicts = json.loads(pathlib.Path('t/out/spec-disagree.json').read_text())
tag = os.environ['MATCH_TAG']
record = {'tags': [tag], 'results': {k:v for k,v in all_verdicts.get('results',{}).items() if k.startswith(tag+'/')}}
(out/'verdicts.json').write_text(json.dumps(record,indent=2)+'\n')
PY
flock -u 8
"$PY" t/score_levels.py "$TAG" --split t/out/loop/split-v5.json --panel clean-182 \
  --verdicts "$OUT/verdicts.json" --min-completeness 0.6 --larger --json "$OUT/problem-levels.json"
"$PY" t/score_levels.py "$TAG" --split t/out/loop/split-v5.json --panel clean-200 \
  --verdicts "$OUT/verdicts.json" --min-completeness 0.6 --larger --json "$OUT/problem-levels-200.json"
touch "$OUT/GRADED"
