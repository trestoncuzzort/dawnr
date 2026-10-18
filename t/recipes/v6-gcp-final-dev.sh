#!/usr/bin/env bash
# Only the completed five-epoch adapter enters this development continuation.
set -euo pipefail
cd /opt/dawnr-run/evaluation
root=t/out/v6-20261018
exec 9>"$root/final-dev.lock"
flock -n 9
python3 - "$root/final-adapter" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
assert json.loads((root/'manifest.json').read_text())['step'] == 1275
assert json.loads((root/'run.json').read_text())['steps'] == 1275
PY
python3 t/recipes/v6_export.py --adapter "$root/final-adapter" \
  --manifest "$root/final-adapter/manifest.json" --llama-dir /opt/dawnr-run/inference/llama.cpp \
  --out "$root/export-final" --name dawnr-v6-20261018 --device cuda
python3 t/recipes/v6_package_gguf.py --export "$root/export-final" \
  --llama-dir /opt/dawnr-run/inference/llama.cpp --stem dawnr-v6-20261018
bash t/recipes/v6-gcp-candidate-dev.sh "$root/export-final" v6-20261018-final-dev dawnr-v6-final
