#!/usr/bin/env bash
# Supplied-specification gates from v5-matched-2026-10-11-grade.sh.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
questions="${1:?frozen 33-question panel}"
generated="${2:?completed v6_spec_route output}"
out="${3:?fresh grading output}"
export T_MIN_KERNELS=7 T_SPARK_JOBS=1 T_SANDBOX=landlock PYTHONUNBUFFERED=1
mkdir -p "$out"
exec 9>"$out/grade.lock"
flock -n 9
test ! -e "$out/GRADED"
test ! -e "$out/kernels.md"
python3 - "$questions" "$generated" "$out" <<'PY'
import hashlib, json, pathlib, sys
questions, generated, out = map(pathlib.Path, sys.argv[1:])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protocol = json.loads((generated/'protocol.json').read_text())
done = json.loads((generated/'completed.json').read_text())
assert protocol['questions_sha256'] == digest(questions)
assert done == {'protocol_sha256': digest(generated/'protocol.json'),
                'answers_sha256': digest(generated/'answers.jsonl'), 'questions': 33}
names = [json.loads(s)['name'] for s in questions.read_text().splitlines() if s.strip()]
answers = [json.loads(s)['name'] for s in (generated/'answers.jsonl').read_text().splitlines()]
assert len(names) == len(set(names)) == len(answers) == len(set(answers)) == 33
assert set(names) == set(answers)
files = sorted(pathlib.Path('t').glob('*.py')) + sorted(pathlib.Path('t/verifiers').rglob('*.py'))
files += [pathlib.Path('t/recipes/v6-grade-spec.sh'), pathlib.Path('t/recipes/bounded-grading-python.py'), questions]
(out/'evaluator.json').write_text(json.dumps({str(p): digest(p) for p in files}, indent=2)+'\n')
PY
python3 t/score_spec_given.py prepare --questions "$questions" --answers "$generated/answers.jsonl" \
  --tasks "$out/tasks" --report "$out/report.json"
if compgen -G "$out/tasks/*.json" > /dev/null; then
  status=0
  python3 t/recipes/bounded-grading-python.py t/run_par.py --tasks "$out/tasks" \
    --out "$out/kernels" --table "$out/kernels.md" --jobs 1 --no-cache > "$out/kernels.log" 2>&1 || status=$?
  test "$status" -le 1 && test -s "$out/kernels.md"
else
  python3 - "$out/kernels.md" <<'PY'
import pathlib, sys
sys.path.insert(0, 't')
import spec_check
pathlib.Path(sys.argv[1]).write_text('| task | '+' | '.join(spec_check.KERNELS)+' |\n')
PY
fi
python3 - "$out" <<'PY'
import json, pathlib, sys
sys.path.insert(0, 't')
import spec_experiment as se, spec_check
out = pathlib.Path(sys.argv[1])
columns, rows = se.parse_kernel_table(out/'kernels.md')
report = json.loads((out/'report.json').read_text())
ready = {n for n, result in report['entries'].items() if result['stage'] == 'ready'}
assert set(columns) == set(spec_check.KERNELS) and set(rows) == ready, 'incomplete kernel coverage'
assert report['questions'] == 33 and not report['stages'].get('unanswered'), 'incomplete answer coverage'
PY
python3 t/score_spec_given.py levels --report "$out/report.json" --table "$out/kernels.md" --json "$out/levels.json"
touch "$out/GRADED"
