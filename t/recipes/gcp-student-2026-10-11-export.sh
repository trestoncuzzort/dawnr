#!/usr/bin/env bash
# Q8_0 export using llama.cpp's converter, pinned before the run's results.
# https://github.com/ggml-org/llama.cpp/tree/23b0202a189c44a54625aadcb37a946dd1d6278d
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/../.."
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=4
OUT=t/out/gcp-student-2026-10-11-s1
test -f "$OUT/TRAINED"
test "$(git -C t/out/llama.cpp rev-parse HEAD)" = 23b0202a189c44a54625aadcb37a946dd1d6278d
mkdir -p "$OUT/export"
t/out/export-venv/bin/python t/out/llama.cpp/convert_hf_to_gguf.py "$OUT/merged" \
  --outfile "$OUT/export/dawnr-gcp-20261011-Q8_0.gguf" --outtype q8_0 --no-mtp \
  --model-name "dawnr 2026-10-11 candidate"
sha256sum "$OUT/export/dawnr-gcp-20261011-Q8_0.gguf" > "$OUT/export/SHA256SUMS"
touch "$OUT/EXPORTED"
