#!/bin/bash
# Both v5 arms of t/PREDICT-2026-10-21-repair-turn.md on the desktop GPU node (tlab): the frozen route (the
# control, tag v5-20261021-dev-desktop) and the same route with --repair 2 (tag v5-20261021-repair-dev), one
# pinned llama-server, one request cache, so every conversation the two arms share is answered once and the
# candidate pays only for its repair calls. Launch as a user unit, never in an ssh foreground.
# Sources: t/recipes/v7_desktop_gen.sh (the desktop route), t/recipes/v7_desktop_p2_annotate.sh (the v5 identity).
set -u
H=/home/t; L=$H/.local/share/dawnr/llama.cpp; D=$H/dawnr; A=$H/v5-repair
PORT=8849
# MODEL=v5 (default) serves the installed shards; MODEL=v7 serves the decomposed-rows export (t/recipes/v7_desktop_gen.sh)
# and seeds the arm's cache from v7's own development requests. IDS overrides the problem panel; PYTHON_ATTEMPTS=0 omits
# --python (for --reference-python runs on training problems).
MODEL=${MODEL:-v5}; IDS=${IDS:-$H/v7/dev-95.txt}; PYTHON_ATTEMPTS=${PYTHON_ATTEMPTS:-3}
if [ "$MODEL" = v7 ]; then
  GGUF=$H/v7/model-Q8_0.gguf; ALIAS=dawnr-v7; SEED=$H/v7/requests
  IDENT="student-v7:$(python3 -c "import json;print(json.load(open('$H/v7/export.json'))['output']['sha256'])"):llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
elif [ "$MODEL" = teacher9b ]; then
  # a teacher audition: Qwen3.5-9B at Q4_K_M (the laptop's copy, Apache-2.0), the same route, judged by the reference check
  GGUF=$H/teachers/Qwen3.5-9B-Q4_K_M.gguf; ALIAS=qwen3.5-9b; SEED=$A/cache-none
  IDENT="teacher-qwen3.5-9b-q4km:$(cat $H/teachers/Qwen3.5-9B-Q4_K_M.gguf.sha):llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
elif [ "$MODEL" = v8 ]; then
  # the v8 export written by t/recipes/v6_export.py under ~/v8/export (model-Q8_0.gguf + export.json)
  GGUF=$H/v8/export/model-Q8_0.gguf; ALIAS=dawnr-v8; SEED=$A/cache-none
  IDENT="student-v8:$(python3 -c "import json;print(json.load(open('$H/v8/export/export.json'))['output']['sha256'])"):llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
else
  GGUF=$H/v5/dawnr-student-00001-of-00003.gguf; ALIAS=dawnr-v5; SEED=$A/requests
  IDENT="student-v5:d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
fi
PYARG=""; [ "$PYTHON_ATTEMPTS" != 0 ] && PYARG="--python $PYTHON_ATTEMPTS"
# PARALLEL server slots and CONCURRENCY route workers (neither is in the route's protocol record; answers are seeded by
# stage and prompt, so a run can resume at a different setting from the same cache). 16/16 for long training-panel runs.
PARALLEL=${PARALLEL:-8}; CONCURRENCY=${CONCURRENCY:-8}
# BATCH is the route's own batch (a spec_first argument, so it is in the cache's protocol record): a chunk waits for its
# slowest reply, so a long training-panel run keeps the slots busier at 64 than at the development default of 16.
# CACHE_RAM caps the server's host-side prompt cache (its default is 8 GiB, which on the 14 GB desktop pushed the server to
# 10.6 GB resident and the run into swap during the 2,597-problem self-distillation on 2026-10-21).
export LD_LIBRARY_PATH=$L PYTHONPATH=$D/t PYTHONUNBUFFERED=1
mkdir -p $A
cd $D || exit 1
rm -f $A/gen.done
[ "$MODEL" != v5 ] || (cd $H/v5 && sha256sum -c --quiet dawnr-student.sha256) || { echo "$(date -u +%FT%TZ) v5 shards fail their checksum" > $A/gen.log; echo 91 > $A/gen.done; exit 1; }
echo "$(date -u +%FT%TZ) start identity=$IDENT" > $A/gen.log
$L/llama-server --model $GGUF --alias $ALIAS --host 127.0.0.1 --port $PORT \
  --n-gpu-layers 99 --threads 16 --threads-batch 16 --parallel $PARALLEL --ctx-size $((PARALLEL * 4096)) \
  --cache-ram ${CACHE_RAM:-1024} \
  --chat-template-kwargs '{"enable_thinking":false}' > $A/server.log 2>&1 &
SP=$!
for i in $(seq 1 240); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; timeout 1 tail -f /dev/null; done
curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo "$(date -u +%FT%TZ) server not healthy" >> $A/gen.log; kill $SP; echo 90 > $A/gen.done; exit 1; }
echo "$(date -u +%FT%TZ) server healthy; routes starting" >> $A/gen.log
route() {
  local tag=$1; shift
  python3 $D/t/recipes/v6_server_route.py --endpoint http://127.0.0.1:$PORT/v1/chat/completions --model $ALIAS \
    --identity "$IDENT" --cache $A/cache-$tag --concurrency $CONCURRENCY \
    -- --tag $tag --ids-file $IDS --pool v5 $PYARG --spec-samples 4 --per-problem 3 --samples 2 \
    --max-new 1024 --batch ${BATCH:-16} "$@" > $A/route-$tag.log 2>&1
  echo "$(date -u +%FT%TZ) $tag rc=$?" >> $A/gen.log
}
# Each arm has its own cache (the route refuses a cache whose protocol record differs), seeded with the 503 requests of
# the v5 development generation of 2026-10-18 (t/out/v6-20261018/v5-dev/requests on the laptop, same identity), so the
# frozen calls replay and only the repair calls are new.
if [ $# -eq 0 ]; then for tag in v5-20261021-dev-desktop v5-20261021-repair-dev; do
  mkdir -p $A/cache-$tag
  ls $A/requests/*.json 2>/dev/null | grep -v protocol.json | xargs -r -I{} ln -f {} $A/cache-$tag/
  rm -f $A/cache-$tag/protocol.json
done; fi
if [ $# -ge 1 ]; then
  # one named arm with its extra route arguments, e.g. `v5-20261021-samples6-dev --spec-samples 6` (the same-budget
  # control: two more plain samples instead of two repair calls)
  tag=$1; shift
  mkdir -p $A/cache-$tag
  ls $SEED/*.json 2>/dev/null | grep -v protocol.json | xargs -r -I{} ln -f {} $A/cache-$tag/ 2>/dev/null
  rm -f $A/cache-$tag/protocol.json
  route $tag "$@"
else
  route v5-20261021-dev-desktop
  route v5-20261021-repair-dev --repair 2
fi
kill $SP 2>/dev/null
echo "$(date -u +%FT%TZ) done" >> $A/gen.log
echo 0 > $A/gen.done
