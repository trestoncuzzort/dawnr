#!/usr/bin/env bash
# The first matched measurement uses only the fixed development panel.
set -euo pipefail
cd /opt/dawnr-run
for attempt in $(seq 1 180); do
  if [ -f inference/INFERENCE_READY ]; then break; fi
  if ! systemctl is-active --quiet dawnr-v6-inference-setup; then
    echo 'Inference setup ended without its checked artifacts' >&2
    exit 1
  fi
  sleep 10
done
test -f inference/INFERENCE_READY
(cd inference/models && echo 'd855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e  dawnr-student.sha256' | sha256sum -c -)
server=$PWD/inference/llama.cpp/build/bin/llama-server
model=$PWD/inference/models/dawnr-student-00001-of-00003.gguf
cd evaluation
export T_SANDBOX=landlock PYTHONUNBUFFERED=1
out=t/out/v6-20261018/v5-dev
mkdir -p "$out"
"$server" --model "$model" --alias dawnr-v5 --host 127.0.0.1 --port 8846 \
  --n-gpu-layers 99 --threads 4 --threads-batch 4 --parallel 8 --ctx-size 65536 \
  --chat-template-kwargs '{"enable_thinking":false}' > "$out/server.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
python3 - <<'PY'
import time, urllib.request
for _ in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8846/health',timeout=2) as response:
            if response.status == 200: break
    except OSError:
        pass
    time.sleep(1)
else: raise SystemExit('v5 server did not become healthy')
PY
python3 t/recipes/v6_server_route.py --endpoint http://127.0.0.1:8846/v1/chat/completions \
  --model dawnr-v5 \
  --identity 'student-v5:d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a' \
  --cache "$out/requests" --concurrency 8 -- \
  --tag v6-20261018-v5-dev --ids-file t/out/v6-20261018/dev-95.txt \
  --pool v5 --python 3 --spec-samples 4 --per-problem 3 --samples 2 --max-new 1024 --batch 16
