#!/bin/bash
# A Cohere model as a teacher for the training problems dawnr fails (Cohere Labs Catalyst Grant; written permission of
# 2026-10-24 to make outputs that pass our checks into training rows, internal/COHERE-GRANT-UPDATES.md). The frozen
# route runs unchanged through t/recipes/cohere_proxy.py: --reference-python --specs-only, the same primer and ten
# candidates per problem as the DeepSeek and 9B lanes. Chunks of 50 with their own tags; the route's cache replays
# finished calls, so a rerun resumes. Spend is guarded by the proxy (the grant ledger's ceiling), not a call count.
#   IDS=out/r61/cohere-pilot-ids.txt SERIES=cohere-cara-20261024 MODEL=command-a-reasoning-08-2025 THINK=2048 PORT=8863 \
#     bash t/recipes/teacher_cohere_specs.sh
# Sources: t/recipes/teacher_bedrock_specs.sh (the chunk loop and route invocation), t/recipes/cohere_proxy.py.
set -u
D=${D:-$HOME/Projects/dawnr}; cd $D || exit 1
IDS=${IDS:?problem id file}; CHUNK=${CHUNK:-50}; START=${START:-0}; SERIES=${SERIES:?tag series}
PORT=${PORT:-8863}; MODEL=${MODEL:-command-a-reasoning-08-2025}; THINK=${THINK:-2048}
CONCURRENCY=${CONCURRENCY:-8}; BATCH=${BATCH:-16}; PRIMER=t/out/v5-repair-20261021/teacher-primer.md
MAX_NEW=${MAX_NEW:-1024}   # the reply's room after the thinking budget; the pilot cut 22% of the reasoning model's replies at 1024
SPEC_SAMPLES=${SPEC_SAMPLES:-9}; SEED_OFFSET=${SEED_OFFSET:-0}
REPRESENTATION=${REPRESENTATION:-surface}
IDENT="teacher-cohere:$MODEL:think$THINK:new$MAX_NEW:2026-10-24"
A=$D/t/out/laptop-runs; O=out/r61/$SERIES; LOG=$O/lane.log; PLOG=$O/proxy.jsonl
V=${V:-/home/t/.claude/jobs/d76813cf/tmp/venv/bin/python}
export PYTHONPATH=$D/t PYTHONUNBUFFERED=1
if [ "$REPRESENTATION" = json-v2 ]; then
  FORMAT_IDENT=$("$V" t/recipes/cohere_task_json_v2.py) || exit 1
  IDENT="$IDENT:$FORMAT_IDENT"
elif [ "$REPRESENTATION" = json ]; then
  FORMAT_IDENT=$("$V" t/recipes/cohere_task_json.py --identity) || exit 1
  IDENT="$IDENT:$FORMAT_IDENT"
elif [ "$REPRESENTATION" != surface ]; then
  echo "unknown teacher representation" >&2; exit 1
fi
mkdir -p $O/chunks $A
# SHARED_PROXY=1: several lanes use one proxy already running on PORT (one process, so the ceiling is exact)
if [ "${SHARED_PROXY:-0}" != 1 ]; then
  $V t/recipes/cohere_proxy.py --port $PORT --model $MODEL --think $THINK --concurrency $CONCURRENCY --tag $SERIES \
    --log $PLOG --representation "$REPRESENTATION" > $O/proxy.log 2>&1 &
  PP=$!; trap 'kill $PP 2>/dev/null' EXIT
fi
for i in $(seq 1 30); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo "$(date -u +%FT%TZ) proxy not up" >> $LOG; exit 1; }
rm -f $O/chunks/ids-*.txt; split -l $CHUNK -d -a 2 --additional-suffix=.txt $IDS $O/chunks/ids-
for f in $O/chunks/ids-*.txt; do
  n=$(basename $f .txt | sed 's/ids-//'); TAG=$SERIES-tc$n
  [ "$((10#$n))" -lt "$START" ] && continue
  [ -s "$A/cache-$TAG/completed.json" ] && continue
  if curl -sf http://127.0.0.1:$PORT/health | grep -q '"spent_usd"'; then
    spent=$(curl -sf http://127.0.0.1:$PORT/health | python3 -c 'import sys,json; print(json.load(sys.stdin)["spent_usd"])')
    python3 -c "import sys; sys.exit(0 if $spent < ${COHERE_CEILING_USD:-950} else 1)" || { echo "$(date -u +%FT%TZ) ledger at ceiling (\$$spent); not starting $TAG" >> $LOG; exit 0; }
  fi
  echo "$(date -u +%FT%TZ) chunk $TAG ($(wc -l < $f) problems; ledger \$${spent:-?})" >> $LOG
  mkdir -p $A/cache-$TAG; rm -f $A/cache-$TAG/protocol.json $A/cache-$TAG/run.lock
  $V t/recipes/v6_server_route.py --endpoint http://127.0.0.1:$PORT/v1/chat/completions --model $MODEL \
    --identity "$IDENT" --cache $A/cache-$TAG --concurrency $CONCURRENCY \
    -- --tag $TAG --ids-file $f --pool v5 --spec-samples $SPEC_SAMPLES --seed-offset $SEED_OFFSET \
    --per-problem 3 --samples 2 --max-new $MAX_NEW --batch $BATCH \
    --reference-python --specs-only --spec-primer $PRIMER > $A/$TAG.route.log 2>&1 || {
      echo "$(date -u +%FT%TZ) route failed for $TAG; paid replies remain in the cache" >> $LOG
      exit 1
    }
  grep -E "spec_first: .*kept specification" $A/$TAG.route.log | tail -1 >> $LOG
done
echo "$(date -u +%FT%TZ) all chunks done" >> $LOG
