#!/usr/bin/env bash
# Same server and Python-first route as the development runs, after selection.
set -euo pipefail
cd /opt/dawnr-run/evaluation
export T_SANDBOX=landlock PYTHONUNBUFFERED=1
arm="${1:?v5 or v6}"
freeze="${2:?candidate selection record}"
export_dir="${3:-}"
case "$arm" in v5|v6) ;; *) exit 2;; esac
root=t/out/v6-20261018
out="$root/$arm-heldout"
tag="v6-20261018-$arm-heldout"
mkdir -p "$out"
exec 9>"$out/generate.lock"
flock -n 9
test ! -e "$out/GENERATED"
identity=$(python3 - "$arm" "$freeze" "$export_dir" "$out" <<'PY'
import hashlib, json, pathlib, subprocess, sys
arm, freeze, export_dir, output = sys.argv[1:]
root, out = pathlib.Path('t/out/v6-20261018'), pathlib.Path(output)
def digest(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()
selected = json.loads(pathlib.Path(freeze).read_text())
assert selected['status'] == 'candidate-frozen' and selected['step'] == 1275
assert selected['development_complete'] is True
for name in ('clean-182.txt', 'spec-heldout.jsonl'):
    assert selected['panels'][name] == digest(root/name), 'frozen panel changed'
ids = (root/'clean-182.txt').read_text().split()
assert len(ids) == len(set(ids)) == 182
revision = 'f1cee9941b0e843ea260bf8dd9a090fbd9711b6a'
llama = pathlib.Path('/opt/dawnr-run/inference/llama.cpp')
assert subprocess.check_output(['git', '-C', str(llama), 'rev-parse', 'HEAD'], text=True).strip() == revision
if arm == 'v5':
    models = pathlib.Path('/opt/dawnr-run/inference/models')
    manifest = models/'dawnr-student.sha256'
    sha = digest(manifest)
    assert sha == 'd855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e'
    for line in manifest.read_text().splitlines():
        expected, name = line.split()
        assert pathlib.Path(name).name == name and digest(models/name) == expected
else:
    exported = pathlib.Path(export_dir)
    receipt = json.loads((exported/'export.json').read_text())
    assert receipt['converter_commit'] == revision and receipt['quantization'] == 'Q8_0'
    assert receipt['adapter']['step'] == 1275
    sha = digest(exported/'model-Q8_0.gguf')
    assert sha == receipt['output']['sha256'] == selected['candidate_gguf_sha256']
    package = json.loads((exported/'release/package.json').read_text())
    assert package['adapter_step'] == 1275 and package['source_gguf_sha256'] == sha
    manifest = exported/'release/dawnr-student.sha256'
    sha = digest(manifest)
    assert sha == package['manifest_sha256'] == selected['candidate_release_manifest_sha256']
    entries = [line.split() for line in manifest.read_text().splitlines()]
    assert entries and entries[0][1] == package['first_shard']
    assert len(entries) == len({name for _,name in entries}) == len(package['files'])
    for expected, name in entries:
        assert pathlib.Path(name).name == name
        assert expected == package['files'][name]['sha256']
        assert digest(exported/'release'/name) == expected
record = {'arm': arm, 'model_identity': f'student-{arm}:{sha}:llama-{revision}',
          'candidate_lock_sha256': digest(freeze), 'panels': selected['panels'],
          'script_sha256': digest('t/recipes/v6-gcp-heldout.sh'),
          'server': {'revision': revision, 'binary_sha256': digest(llama/'build/bin/llama-server'),
                     'gpu_layers': 99, 'threads': 4,
                     'threads_batch': 4, 'parallel': 8, 'ctx_size': 65536,
                     'enable_thinking': False}}
path = out/'generation.json'
if path.exists(): assert json.loads(path.read_text()) == record, 'generation identity changed'
path.write_text(json.dumps(record, indent=2)+'\n')
print(record['model_identity'])
PY
)
server=/opt/dawnr-run/inference/llama.cpp/build/bin/llama-server
if [ "$arm" = v5 ]; then
  model=/opt/dawnr-run/inference/models/dawnr-student-00001-of-00003.gguf
else
  model="$export_dir/release/$(awk 'NR == 1 {print $2}' "$export_dir/release/dawnr-student.sha256")"
fi
"$server" --model "$model" --alias "dawnr-$arm" --host 127.0.0.1 --port 8846 \
  --n-gpu-layers 99 --threads 4 --threads-batch 4 --parallel 8 --ctx-size 65536 \
  --chat-template-kwargs '{"enable_thinking":false}' > "$out/server.log" 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true' EXIT
python3 - "$out" <<'PY'
import hashlib, json, pathlib, sys, time, urllib.request
for _ in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8846/health', timeout=2) as response:
            if response.status == 200: break
    except OSError: pass
    time.sleep(1)
else: raise SystemExit('model server did not become ready')
with urllib.request.urlopen('http://127.0.0.1:8846/props', timeout=5) as response:
    props = json.load(response)
assert props['total_slots'] == 8
assert hashlib.sha256(props['chat_template'].encode()).hexdigest() == \
       'a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715'
pathlib.Path(sys.argv[1], 'server-props.json').write_text(json.dumps(props, indent=2)+'\n')
PY
python3 t/recipes/v6_server_route.py --endpoint http://127.0.0.1:8846/v1/chat/completions \
  --model "dawnr-$arm" --identity "$identity" --cache "$out/requests" --concurrency 8 -- \
  --tag "$tag" --ids-file "$root/clean-182.txt" \
  --pool v5 --python 3 --spec-samples 4 --per-problem 3 --samples 2 --max-new 1024 --batch 16
python3 t/recipes/v6_spec_route.py --endpoint http://127.0.0.1:8846/v1/chat/completions \
  --model "dawnr-$arm" --identity "$identity" --questions "$root/spec-heldout.jsonl" --out "$out/spec"
test -s "$out/requests/completed.json" && test -s "$out/spec/completed.json"
touch "$out/GENERATED"
