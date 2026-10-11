#!/usr/bin/env bash
# Replay the supplied correct programs through the same held-out instrument.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export T_SANDBOX=landlock CUDA_VISIBLE_DEVICES= T_SPARK_JOBS=1 PYTHONUNBUFFERED=1
PY="${PYTHON:-python3}"
OUT=t/out/gcp-student-2026-10-11-s1
test ! -e "$OUT/ceiling-kernels.md" || { echo "ceiling table already exists" >&2; exit 2; }
"$PY" - <<'PY'
import json, pathlib
out = pathlib.Path('t/out/gcp-student-2026-10-11-s1')
questions = [json.loads(l) for l in (out/'spec-heldout.jsonl').read_text().splitlines()]
(out/'ceiling-answers.jsonl').write_text(''.join(json.dumps({'name':q['name'],'reply':q['chosen']})+'\n' for q in questions))
PY
"$PY" t/score_spec_given.py prepare --questions "$OUT/spec-heldout.jsonl" \
  --answers "$OUT/ceiling-answers.jsonl" --tasks "$OUT/ceiling-tasks" --report "$OUT/ceiling-report.json"
status=0
"$PY" t/run_par.py --tasks "$OUT/ceiling-tasks" --out "$OUT/ceiling-kernels" \
  --table "$OUT/ceiling-kernels.md" --jobs 4 --no-cache > "$OUT/ceiling-kernels.log" 2>&1 || status=$?
test "$status" -le 1 && test -s "$OUT/ceiling-kernels.md"
"$PY" t/score_spec_given.py levels --report "$OUT/ceiling-report.json" --table "$OUT/ceiling-kernels.md" \
  --json "$OUT/ceiling-levels.json"
touch "$OUT/CEILING-GRADED"
