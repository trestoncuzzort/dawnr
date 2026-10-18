#!/usr/bin/env bash
# Same fixed development route and server settings as v6-gcp-dev.sh.
set -euo pipefail
cd /opt/dawnr-run/evaluation
export T_SANDBOX=landlock PYTHONUNBUFFERED=1
export_dir="${1:?export directory}"
tag="${2:?unique development tag}"
alias="${3:?model alias}"
out="t/out/v6-20261018/$tag"
mkdir -p "$out"
identity=$(python3 - "$export_dir" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
receipt = json.loads((root/'export.json').read_text())
assert receipt['converter_commit'] == 'f1cee9941b0e843ea260bf8dd9a090fbd9711b6a'
assert receipt['quantization'] == 'Q8_0'
model = root/receipt['output']['filename']
h = hashlib.sha256()
with model.open('rb') as stream:
    for block in iter(lambda: stream.read(1024*1024), b''):
        h.update(block)
assert h.hexdigest() == receipt['output']['sha256']
print('student-v6:'+h.hexdigest()+':llama-'+receipt['converter_commit'])
PY
)
server=/opt/dawnr-run/inference/llama.cpp/build/bin/llama-server
"$server" --model "$export_dir/model-Q8_0.gguf" --alias "$alias" --host 127.0.0.1 --port 8846 \
  --n-gpu-layers 99 --threads 4 --threads-batch 4 --parallel 8 --ctx-size 65536 \
  --chat-template-kwargs '{"enable_thinking":false}' > "$out/server.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
python3 - "$out" <<'PY'
import hashlib, json, pathlib, sys, time, urllib.request
for _ in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8846/health', timeout=2) as response:
            if response.status == 200:
                break
    except OSError:
        pass
    time.sleep(1)
else:
    raise SystemExit('candidate server did not become healthy')
with urllib.request.urlopen('http://127.0.0.1:8846/props', timeout=5) as response:
    props = json.load(response)
pathlib.Path(sys.argv[1], 'server-props.json').write_text(json.dumps(props, indent=2)+'\n')
assert props['total_slots'] == 8
assert hashlib.sha256(props['chat_template'].encode()).hexdigest() == \
       'a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715', 'v5 chat template changed'
PY
python3 t/recipes/v6_server_route.py --endpoint http://127.0.0.1:8846/v1/chat/completions \
  --model "$alias" --identity "$identity" --cache "$out/requests" --concurrency 8 -- \
  --tag "$tag" --ids-file t/out/v6-20261018/dev-95.txt \
  --pool v5 --python 3 --spec-samples 4 --per-problem 3 --samples 2 --max-new 1024 --batch 16
