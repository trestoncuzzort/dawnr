#!/usr/bin/env bash
# Resume only the programming stage after the registered lowering-memory failure.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
ARM="${1:?give v5 or recovered}"
case "$ARM" in v5|recovered) ;; *) exit 2 ;; esac
OUT="t/out/v5-matched-20261011/$ARM"
test -f "$OUT/GENERATED"
test ! -e "$OUT/GRADED"
test ! -e "t/out/spec-experiment/v5-matched-20261011-$ARM/kernels.md"
test ! -e "$OUT/attempt-unbounded"
mkdir "$OUT/attempt-unbounded"
for name in grade.log problem-kernels.log problem-kernels; do
  if [ -e "$OUT/$name" ]; then mv "$OUT/$name" "$OUT/attempt-unbounded/$name"; fi
done
export T_LOWER_MEMORY_MB=4096
export PYTHON="$PWD/t/recipes/bounded-grading-python.py"
python3 - "$OUT" <<'PY'
import hashlib,json,pathlib,sys
files=['t/recipes/bounded-grading-python.py','t/recipes/v5-matched-2026-10-11-grade.sh',
       't/recipes/v5-matched-2026-10-11-retry.sh']
record={'lowering_address_space_mib':4096,'kernel_limits_restored':True,
        'specifications':'unchanged completed stage, bound by spec-stage.json',
        'files':{p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in files}}
(pathlib.Path(sys.argv[1])/'program-evaluator.json').write_text(json.dumps(record,indent=2)+'\n')
PY
status=0
bash t/recipes/v5-matched-2026-10-11-grade.sh "$ARM" all > "$OUT/grade.log" 2>&1 || status=$?
printf '%s\n' "$status" > "$OUT/GRADE-EXIT"
exit "$status"
