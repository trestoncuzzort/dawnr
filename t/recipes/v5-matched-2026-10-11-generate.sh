#!/usr/bin/env bash
# Existing generation interfaces, matched Q8_0 models and one greedy reply each.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export CUDA_VISIBLE_DEVICES= T_SANDBOX=landlock PYTHONUNBUFFERED=1
ARM="${1:?give v5 or recovered}"
case "$ARM" in
  v5) MODEL="$HOME/.local/share/dawnr/models/dawnr-student-00001-of-00003.gguf"; PORT=8821 ;;
  recovered) MODEL=t/out/gcp-student-2026-10-11-s1/export/dawnr-gcp-20261011-Q8_0.gguf; PORT=8822 ;;
  *) exit 2 ;;
esac
PY="${PYTHON:-python3}"
OUT="t/out/v5-matched-20261011/$ARM"
TAG="v5-matched-20261011-$ARM"
mkdir -p "$OUT" t/out/v5-rebuild-20261011
exec 9>"$OUT/generate.lock"
flock -n 9
SERVER="$HOME/.local/share/dawnr/llama.cpp/llama-server"
"$SERVER" --model "$MODEL" --alias "$TAG" --host 127.0.0.1 --port "$PORT" \
  --n-gpu-layers 0 --threads 16 --threads-batch 16 --parallel 1 --ctx-size 8192 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  > "t/out/v5-rebuild-20261011/server-$ARM.log" 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true' EXIT
"$PY" - "$PORT" <<'PY'
import sys,time,urllib.request
for _ in range(90):
    try:
        with urllib.request.urlopen('http://127.0.0.1:'+sys.argv[1]+'/health',timeout=2) as r:
            if r.status == 200: break
    except OSError: pass
    time.sleep(2)
else: raise SystemExit('model server did not become ready')
PY
"$PY" t/score_spec_given.py ask --model "$TAG" --host "127.0.0.1:$PORT" \
  --questions t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl \
  --out "$OUT/spec-answers.jsonl" --system s1 --max-new 1024
"$PY" t/spec_experiment.py generate --model "$TAG" --tag "$TAG" --pool v5 \
  --api openai --flavour llamacpp --host "127.0.0.1:$PORT" --prompt s2 \
  --ids-file t/out/v5-matched-20261011/clean-200.txt --temperature 0 --seed 1 \
  --num-predict 1024 --num-ctx 8192 --top-p 0.95 --top-k 0 --repeat-penalty 1 --jobs 1
"$PY" - "$OUT" "$TAG" <<'PY'
import json,pathlib,sys
out=pathlib.Path(sys.argv[1]); tag=sys.argv[2]
questions=[json.loads(l)['name'] for l in pathlib.Path('t/out/gcp-student-2026-10-11-s1/spec-heldout.jsonl').read_text().splitlines()]
answers=[json.loads(l)['name'] for l in (out/'spec-answers.jsonl').read_text().splitlines()]
assert len(answers)==len(set(answers))==33 and set(answers)==set(questions)
ids=set(pathlib.Path('t/out/v5-matched-20261011/clean-200.txt').read_text().split())
assert len(ids)==200 and {p.stem for p in (pathlib.Path('t/out/spec-experiment')/tag/'raw').glob('*.json')}==ids
(out/'GENERATED').touch()
PY
