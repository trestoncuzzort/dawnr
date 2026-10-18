#!/usr/bin/env bash
# Export the completed corrective stage and use the unchanged development route.
set -euo pipefail
cd /opt/dawnr-run/evaluation
root=t/out/v6-20261018
exec 9>"$root/corrective-dev.lock"
flock -n 9
python3 - "$root/corrective-adapter" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
manifest = json.loads((root / 'manifest.json').read_text())
run = json.loads((root / 'run.json').read_text())
initialization = json.loads((root / 'initialization.json').read_text())
assert manifest['kind'] == 'corrective-sft' and manifest['step'] == run['steps'] == 249
assert manifest['parent_step'] == initialization['parent_step'] == 400
assert manifest['data_sha256'] == run['sft_sha256'] == '8aa1b7528363ebfa149e9b6a18ea9081c4904ff3d8687c240a9ea511d45c4794'
assert manifest['parent_files'] == initialization['parent_files'] == {
    'adapter_config.json': '9c8bb1b245107292a495fde1a14d2323ee70eb985a5bed887a865719e65ac178',
    'adapter_model.safetensors': 'af314c4595d8e648b1a219097d5985ba30b5afb420733ae9da600bb967b54583'}
assert (run['recipe']['lr'], run['recipe']['epochs'], run['rows_used']) == (2e-5, 1, 3980)
assert not initialization['parent_optimizer_loaded'] and not initialization['parent_data_cursor_loaded']
PY
python3 t/recipes/v6_export.py --adapter "$root/corrective-adapter" \
  --manifest "$root/corrective-adapter/manifest.json" --llama-dir /opt/dawnr-run/inference/llama.cpp \
  --out "$root/export-corrective" --name dawnr-v6-20261018-corrective --device cuda
python3 t/recipes/v6_package_gguf.py --export "$root/export-corrective" \
  --llama-dir /opt/dawnr-run/inference/llama.cpp --stem dawnr-v6-20261018-corrective
bash t/recipes/v6-gcp-candidate-dev.sh "$root/export-corrective" v6-20261018-corrective-dev dawnr-v6-corrective
