#!/bin/bash
# DeepSeek v3.2 on Amazon Bedrock as the second teacher for the failed training problems (MIT weights, allowed for
# training rows), through t/recipes/bedrock_proxy.py so the frozen route runs unchanged: --reference-python
# --specs-only, the same primer and ten candidates per problem as the 9B lane. Chunks of 50 with their own tags;
# the route's cache replays finished calls. Stops at MAX_CALLS logged calls (the spend guard; read the real spend
# in Cost Explorer the next day, never estimate it). 2026-10-22, after `aws login` restored the session.
#   bash t/recipes/teacher_bedrock_specs.sh            env: IDS=out/v9/teacher-ids-aws.txt CHUNK=50 START=0
#                                                           SERIES=teacher-ds32-20261022 MAX_CALLS=12000 PORT=8853
# Sources: t/recipes/teacher_train_specs.sh (the chunk loop), t/recipes/laptop_route.sh (the route invocation).
set -u
export PATH=$HOME/.local/bin:$PATH AWS_PAGER=""
D=$HOME/Projects/dawnr; cd $D || exit 1
IDS=${IDS:-out/v9/teacher-ids-aws.txt}; CHUNK=${CHUNK:-50}; START=${START:-0}; SERIES=${SERIES:-teacher-ds32-20261022}
MAX_CALLS=${MAX_CALLS:-12000}; PORT=${PORT:-8853}; MODEL=${MODEL:-deepseek.v3.2}; REGION=${REGION:-us-east-1}
CONCURRENCY=${CONCURRENCY:-4}; BATCH=${BATCH:-16}; PRIMER=t/out/v5-repair-20261021/teacher-primer.md
IDENT="teacher-deepseek-v3.2-bedrock:$MODEL:$REGION:2026-10-22"
A=$D/t/out/laptop-runs; LOG=out/v9/teacher-bedrock.log; PLOG=out/v9/bedrock-proxy.jsonl
V=${V:-/home/t/.claude/jobs/d76813cf/tmp/venv/bin/python}
export PYTHONPATH=$D/t PYTHONUNBUFFERED=1
mkdir -p out/v9/chunks-ds $A
$V t/recipes/bedrock_proxy.py --port $PORT --model $MODEL --region $REGION --concurrency $CONCURRENCY --log $PLOG > out/v9/bedrock-proxy.log 2>&1 &
PP=$!; trap 'kill $PP 2>/dev/null' EXIT
for i in $(seq 1 30); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 1; done
curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo "$(date -u +%FT%TZ) proxy not up" >> $LOG; exit 1; }
rm -f out/v9/chunks-ds/ids-*.txt; split -l $CHUNK -d -a 2 --additional-suffix=.txt $IDS out/v9/chunks-ds/ids-
for f in out/v9/chunks-ds/ids-*.txt; do
  n=$(basename $f .txt | sed 's/ids-//'); TAG=$SERIES-tc$n
  [ "$((10#$n))" -lt "$START" ] && continue
  [ -s t/out/spec-experiment/$TAG/kept-specs.jsonl ] && continue
  calls=$(grep -c '"ok": true' $PLOG 2>/dev/null || echo 0)
  [ "$calls" -ge "$MAX_CALLS" ] && { echo "$(date -u +%FT%TZ) MAX_CALLS reached ($calls); not starting $TAG" >> $LOG; exit 0; }
  echo "$(date -u +%FT%TZ) chunk $TAG ($(wc -l < $f) problems; $calls calls so far)" >> $LOG
  mkdir -p $A/cache-$TAG; rm -f $A/cache-$TAG/protocol.json $A/cache-$TAG/run.lock
  $V t/recipes/v6_server_route.py --endpoint http://127.0.0.1:$PORT/v1/chat/completions --model $MODEL \
    --identity "$IDENT" --cache $A/cache-$TAG --concurrency $CONCURRENCY \
    -- --tag $TAG --ids-file $f --pool v5 --spec-samples 9 --per-problem 3 --samples 2 --max-new 1024 --batch $BATCH \
    --reference-python --specs-only --spec-primer $PRIMER > $A/$TAG.route.log 2>&1
  grep -E "spec_first: .*kept specification" $A/$TAG.route.log | tail -1 >> $LOG
done
echo "$(date -u +%FT%TZ) all chunks done" >> $LOG
