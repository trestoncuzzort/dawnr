#!/usr/bin/env bash
# VM side, once: the environment of t/PREDICT-2026-10-11-gcp-student.md (pinned image, same package pins),
# the base weights and the pinned llama.cpp converter. Run from ~/dawnr on the VM.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false
OUT=t/out/udebug-student-2026-10-13
mkdir -p "$OUT"
python3 -m venv --system-site-packages t/out/gcp-venv
PY=t/out/gcp-venv/bin/python
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q "transformers==5.17.0" "peft==0.21.2" "bitsandbytes==0.50.2" "accelerate==1.15.0" \
  "jinja2==3.1.6" "huggingface_hub" "gguf" "sentencepiece" "protobuf"
"$PY" -m pip install -q "torchaudio==2.9.1" --index-url https://download.pytorch.org/whl/cu129
"$PY" -m pip freeze > "$OUT/environment.txt"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > "$OUT/gpu.csv"
"$PY" - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3.5-4B', revision='851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a',
                  local_dir='t/out/gcp-base', allow_patterns=['*.json', '*.safetensors', '*.jinja', '*.txt', 'LICENSE*'])
PY
test -d t/out/llama.cpp || git clone -q https://github.com/ggml-org/llama.cpp.git t/out/llama.cpp
git -C t/out/llama.cpp checkout -q 23b0202a189c44a54625aadcb37a946dd1d6278d
touch "$OUT/SETUP-DONE"
