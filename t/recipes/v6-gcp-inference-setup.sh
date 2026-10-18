#!/usr/bin/env bash
# Build the same llama.cpp revision as the installed v5 server, with CUDA for L4.
# https://github.com/ggml-org/llama.cpp/tree/f1cee9941b0e843ea260bf8dd9a090fbd9711b6a
# Run from the remote dawnr working directory. No training process is started here.
set -euo pipefail
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends cmake build-essential git curl libssl-dev pkg-config
mkdir -p inference/models
cd inference
revision=f1cee9941b0e843ea260bf8dd9a090fbd9711b6a
if [ ! -d llama.cpp/.git ]; then
  git init llama.cpp
  git -C llama.cpp remote add origin https://github.com/ggml-org/llama.cpp.git
fi
git -C llama.cpp fetch --depth 1 origin "$revision"
git -C llama.cpp checkout --detach "$revision"
cmake -S llama.cpp -B llama.cpp/build -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
  -DCMAKE_CUDA_ARCHITECTURES=89 -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build llama.cpp/build --target llama-server llama-quantize llama-gguf-split -j 4
llama.cpp/build/bin/llama-server --version
cd models
base=https://github.com/trestoncuzzort/dawnr/releases/download/rolling
for name in dawnr-student.sha256 dawnr-student-00001-of-00003.gguf \
            dawnr-student-00002-of-00003.gguf dawnr-student-00003-of-00003.gguf; do
  if [ ! -s "$name" ]; then
    asset=$name
    [ "$name" != dawnr-student.sha256 ] || asset=dawnr-v5-baseline.sha256
    curl -fL --retry 3 -o "$name.part" "$base/$asset"
    mv "$name.part" "$name"
  fi
done
echo 'd855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e  dawnr-student.sha256' | sha256sum -c -
sha256sum -c dawnr-student.sha256
touch ../INFERENCE_READY
