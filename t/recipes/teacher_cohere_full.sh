#!/bin/bash
# The full Cohere teacher run after the pilot: one shared proxy (so the grant ledger's ceiling is exact) and LANES lanes
# of t/recipes/teacher_cohere_specs.sh on interleaved id lists (out/r61/cohere-full-ids-K.txt), each a user unit.
#   MODEL=command-a-plus-05-2026 THINK=2048 bash t/recipes/teacher_cohere_full.sh
set -u
D=${D:-$HOME/Projects/dawnr}; cd $D || exit 1
MODEL=${MODEL:?model}; THINK=${THINK:-2048}; LANES=${LANES:-6}; PORT=${PORT:-8865}; SHORT=${SHORT:-$(echo $MODEL | cut -d- -f1-3)}
MAX_NEW=${MAX_NEW:-1024}; CPUS=${CPUS:-}   # CPUS=12-23 keeps the lanes off the cores a training run uses
AFF=(); [ -n "$CPUS" ] && AFF=(-p CPUAffinity=$CPUS)
V=${V:-/home/t/.claude/jobs/d76813cf/tmp/venv/bin/python}
mkdir -p out/r61/cohere-full
systemctl --user reset-failed 2>/dev/null
systemd-run --user --unit dawnr-cohere-proxy --collect -p WorkingDirectory=$D "${AFF[@]}" \
  $V t/recipes/cohere_proxy.py --port $PORT --model $MODEL --think $THINK --concurrency $((LANES * 8)) \
  --tag cohere-full-$SHORT --log $D/out/r61/cohere-full/proxy.jsonl
for i in $(seq 1 30); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:$PORT/health || { echo "proxy not up"; exit 1; }
for k in $(seq 0 $((LANES - 1))); do
  systemd-run --user --unit dawnr-cohere-lane-$k --collect -p WorkingDirectory=$D "${AFF[@]}" --setenv=V=$V --setenv=MAX_NEW=$MAX_NEW --setenv=D=$D \
    --setenv=SHARED_PROXY=1 --setenv=PORT=$PORT --setenv=MODEL=$MODEL --setenv=THINK=$THINK --setenv=CONCURRENCY=8 \
    --setenv=IDS=out/r61/cohere-full-ids-$k.txt --setenv=SERIES=cohere-full-$SHORT-$k \
    /usr/bin/bash t/recipes/teacher_cohere_specs.sh
done
