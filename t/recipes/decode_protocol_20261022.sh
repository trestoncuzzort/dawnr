#!/bin/bash
# The three-decode protocol's first application (t/PREDICT-2026-10-22-seed-variance.md, Result, 2026-10-22): the two
# decodes that complete three for v5 and for v8 on the development panel, one after the other on the laptop's GPU.
#   v5 seed offset 2000 (its first decode is the control, its second the seedoff1000 arm); v8 seed offsets 1000 and 2000
#   (its first decode is v8-20261021-dev). Greedy calls replay from each model's first-decode cache.
set -u
D=$HOME/Projects/dawnr; cd $D || exit 1
V5=$HOME/.local/share/dawnr/models/dawnr-student-00001-of-00003.gguf
V5ID=$(sed -n 's/.*identity=//p' t/out/laptop-runs/v5-20261022-seedoff1000.log | head -1)
V8=$D/t/out/v8-export/model-Q8_0.gguf
V8ID=$(sed -n 's/.*identity=//p' t/out/laptop-runs/v8-20261021-dev.log | head -1)
[ -n "$V5ID" ] && [ -n "$V8ID" ] || { echo "identity missing" >> t/out/decode-arms.log; exit 1; }
bash t/recipes/decode_arm.sh v5-20261022-seedoff2000 $V5 "$V5ID" 2000 t/out/v6-20261018/v5-dev/requests
bash t/recipes/decode_arm.sh v8-20261022-seedoff1000 $V8 "$V8ID" 1000 t/out/laptop-runs/cache-v8-20261021-dev
bash t/recipes/decode_arm.sh v8-20261022-seedoff2000 $V8 "$V8ID" 2000 t/out/laptop-runs/cache-v8-20261021-dev
echo "$(date -u +%FT%TZ) decode protocol complete" >> t/out/decode-arms.log
