#!/bin/bash
# The frozen route on the LAPTOP's GPU (RTX 5050 Laptop, 8 GB): the pinned llama-server bundle at
# ~/.local/share/dawnr/llama.cpp, a model GGUF, the development panel, one request cache per tag (optionally seeded from
# another cache), outputs under t/out/spec-experiment/<tag> as everywhere else. Launch as a user unit, never in the
# terminal scope (an OOM kill there takes the session). 2026-10-21, after the user asked for the laptop's card and the
# desktop's to share the load. Sources: t/recipes/v5_desktop_repair.sh (the desktop twin), t/recipes/v7_desktop_gen.sh.
#   laptop_route.sh TAG GGUF IDENT [route args...]      env: SEED=<cache dir to seed from> PARALLEL=4 CONCURRENCY=4
set -u
TAG=${1:?tag}; GGUF=${2:?gguf}; IDENT=${3:?identity}; shift 3
D=/home/t/Projects/dawnr; L=/home/t/.local/share/dawnr/llama.cpp; A=$D/t/out/laptop-runs; PORT=${PORT:-8851}
PARALLEL=${PARALLEL:-4}; CONCURRENCY=${CONCURRENCY:-4}; BATCH=${BATCH:-16}; SEED=${SEED:-}; SLOT_CTX=${SLOT_CTX:-4096}
IDS=${IDS:-$D/t/out/v6-20261018/dev-95.txt}; PYTHON_ATTEMPTS=${PYTHON_ATTEMPTS:-3}
PYARG=""; [ "$PYTHON_ATTEMPTS" != 0 ] && PYARG="--python $PYTHON_ATTEMPTS"
export LD_LIBRARY_PATH=$L PYTHONPATH=$D/t PYTHONUNBUFFERED=1
mkdir -p $A/cache-$TAG; cd $D || exit 1
rm -f $A/$TAG.done
if [ -n "$SEED" ] && [ -d "$SEED" ]; then ls $SEED/*.json 2>/dev/null | grep -v protocol.json | xargs -r -I{} ln -f {} $A/cache-$TAG/ 2>/dev/null; fi
rm -f $A/cache-$TAG/protocol.json $A/cache-$TAG/run.lock
echo "$(date -u +%FT%TZ) start $TAG identity=$IDENT" > $A/$TAG.log
$L/llama-server --model $GGUF --alias dawnr-route --host 127.0.0.1 --port $PORT --n-gpu-layers 99 --threads 8 --threads-batch 8 \
  --parallel $PARALLEL --ctx-size $((PARALLEL * SLOT_CTX)) --cache-ram 512 --chat-template-kwargs '{"enable_thinking":false}' > $A/$TAG.server.log 2>&1 &
SP=$!
for i in $(seq 1 240); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; timeout 1 tail -f /dev/null; done
curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo "$(date -u +%FT%TZ) server not healthy" >> $A/$TAG.log; kill $SP; echo 90 > $A/$TAG.done; exit 1; }
python3 $D/t/recipes/v6_server_route.py --endpoint http://127.0.0.1:$PORT/v1/chat/completions --model dawnr-route \
  --identity "$IDENT" --cache $A/cache-$TAG --concurrency $CONCURRENCY \
  -- --tag $TAG --ids-file $IDS --pool v5 $PYARG --spec-samples 4 --per-problem 3 --samples 2 --max-new 1024 --batch $BATCH "$@" \
  > $A/$TAG.route.log 2>&1
RC=$?
kill $SP 2>/dev/null
echo "$(date -u +%FT%TZ) $TAG rc=$RC" >> $A/$TAG.log
echo $RC > $A/$TAG.done
