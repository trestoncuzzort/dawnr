#!/bin/bash
# Runs on the desktop GPU box (tlab: real kernel, bubblewrap via t/apparmor-bwrap.sh, the pinned llama.cpp CUDA
# bundle at ~/.local/share/dawnr/llama.cpp, the v7 Q8 export and the 95-id panel under ~/v7). Modal's gVisor has no
# sandbox, so this is where generation ran on 2026-10-20. Launch as a system unit, never in an ssh foreground.
# v7 development generation on the desktop: the frozen Modal route (t/recipes/v7_modal_devrun.py generate()) with desktop paths.
set -u
H=/home/t; L=$H/.local/share/dawnr/llama.cpp; D=$H/dawnr; V=$H/v7
GGUF=$V/model-Q8_0.gguf
SHA=$(python3 -c "import json;print(json.load(open('$V/export.json'))['output']['sha256'])")
IDENT="student-v7:$SHA:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
TAG=v7-20261019-dev
export LD_LIBRARY_PATH=$L PYTHONPATH=$D/t PYTHONUNBUFFERED=1
cd $D || exit 1
rm -f $V/gen.done
echo "$(date -u +%FT%TZ) start identity=$IDENT" > $V/gen.log
$L/llama-server --model $GGUF --alias dawnr-v7 --host 127.0.0.1 --port 8847 --n-gpu-layers 99 --threads 16 --threads-batch 16 \
  --parallel 8 --ctx-size 32768 --chat-template-kwargs '{"enable_thinking":false}' > $V/server.log 2>&1 &
SP=$!
for i in $(seq 1 240); do curl -sf http://127.0.0.1:8847/health >/dev/null && break; timeout 1 tail -f /dev/null; done
curl -sf http://127.0.0.1:8847/health >/dev/null || { echo "$(date -u +%FT%TZ) server not healthy" >> $V/gen.log; kill $SP; echo 90 > $V/gen.done; exit 1; }
echo "$(date -u +%FT%TZ) server healthy; route starting" >> $V/gen.log
python3 $D/t/recipes/v6_server_route.py --endpoint http://127.0.0.1:8847/v1/chat/completions --model dawnr-v7 \
  --identity "$IDENT" --cache $V/requests --concurrency 8 \
  -- --tag $TAG --ids-file $V/dev-95.txt --pool v5 --python 3 --spec-samples 4 --per-problem 3 --samples 2 --max-new 1024 --batch 16 \
  > $V/route.log 2>&1
RC=$?
kill $SP 2>/dev/null
echo "$(date -u +%FT%TZ) route rc=$RC" >> $V/gen.log
echo $RC > $V/gen.done
