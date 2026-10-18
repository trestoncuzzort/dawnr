#!/usr/bin/env bash
# One registered midpoint of preserved checkpoints, evaluated only on development.
set -euo pipefail
cd /opt/dawnr-run/evaluation
root=t/out/v6-20261018
exec 9>"$root/average-dev.lock"
flock -n 9
python3 - "$root" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
assert json.loads((root/'final-adapter/manifest.json').read_text())['step'] == 1275
assert json.loads((root/'checkpoint-400/manifest.json').read_text())['step'] == 400
assert not (root/'candidate-frozen.json').exists(), 'candidate selection already closed'
PY
python3 t/recipes/v6_export.py --adapter "$root/final-adapter" \
  --manifest "$root/final-adapter/manifest.json" \
  --average-adapter "$root/checkpoint-400" --average-manifest "$root/checkpoint-400/manifest.json" \
  --llama-dir /opt/dawnr-run/inference/llama.cpp --out "$root/export-average" \
  --name dawnr-v6-20261018-average --device cuda
bash t/recipes/v6-gcp-candidate-dev.sh "$root/export-average" v6-20261018-average-dev dawnr-v6-average
