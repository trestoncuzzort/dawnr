#!/bin/bash
# The primed Qwen3.5-9B teacher writes specifications for TRAINING problems the student failed (out/v9/teacher-ids.txt,
# 2,061 ids: tried by the self-distillation run, nothing kept at the strict floor), in chunks of 100 on the laptop's GPU,
# each chunk its own tag so a stopped run keeps every finished chunk. The reference check keeps only candidates that
# agree with the problem's own solution (spec_first --reference-python --specs-only); the strict re-check
# (t/recipes/v9_strict_specs.py) is applied to the kept files afterwards. No new chunk starts after STOP_AT (epoch
# seconds) or once STOP_FILE exists, so the GPU is free for the tandem units' decodes. Resume by running again: chunks
# with a kept file are skipped, and the route's cache replays finished calls of a chunk that was cut short.
#   STOP_AT=$(date -d '13:45 UTC' +%s) bash t/recipes/teacher_train_specs.sh
# Sources: t/recipes/laptop_route.sh; the audition t/out/laptop-runs/teacher9b-20261021-primer.log (same primer, the
# same 10 candidates per problem); t/PREDICT-2026-10-22-v9-strict-rows.md (P3: the teacher rows are v10's data).
set -u
D=$HOME/Projects/dawnr; cd $D || exit 1
IDS=${IDS:-out/v9/teacher-ids-ordered.txt}; CHUNK=${CHUNK:-50}; START=${START:-0}; STOP_AT=${STOP_AT:-0}; STOP_FILE=${STOP_FILE:-out/v9/teacher.stop}
# 2026-10-22 13:45Z: the slice's statements grow with the id (chunk 02 of 100: 958 of 1,012 prompts over 3,500 tokens, 137
# truncated at a 4,096 slot, 2 problems kept); two slots of 8,192 keep the same KV memory on the 8 GB card.
# 14:25Z: the remaining failed problems are ordered by statement size (out/v9/teacher-ids-ordered.txt): short ones kept 16
# and 17 of 100, long ones 2 of 100 and 3 of 50 even untruncated (43 of 505 replies parsed), so the best yield goes first.
SERIES=${SERIES:-teacher9b-20261022c}; export PARALLEL=${PARALLEL:-2} CONCURRENCY=${CONCURRENCY:-2} SLOT_CTX=${SLOT_CTX:-8192}
GGUF=$HOME/.local/share/dawnr/models/Qwen3.5-9B-Q4_K_M.gguf
IDENT="teacher-qwen3.5-9b-q4km:8c4cc24f54473f3d4e080d4ec7fd2a40d0bbec0f94f3c807cd62694905357d54:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
PRIMER=t/out/v5-repair-20261021/teacher-primer.md
LOG=out/v9/teacher.log
mkdir -p out/v9/chunks
rm -f out/v9/chunks/ids-*.txt; split -l $CHUNK -d -a 2 --additional-suffix=.txt $IDS out/v9/chunks/ids-   # re-split every run; a new IDS needs a new SERIES
for f in out/v9/chunks/ids-*.txt; do
  n=$(basename $f .txt | sed 's/ids-//'); TAG=$SERIES-tc$n
  [ "$((10#$n))" -lt "$START" ] && continue
  [ -s t/out/spec-experiment/$TAG/kept-specs.jsonl ] && continue
  [ -f $STOP_FILE ] && { echo "$(date -u +%FT%TZ) stop file; not starting $TAG" >> $LOG; exit 0; }
  [ "$STOP_AT" != 0 ] && [ "$(date +%s)" -ge "$STOP_AT" ] && { echo "$(date -u +%FT%TZ) past STOP_AT; not starting $TAG" >> $LOG; exit 0; }
  pgrep -f "[l]lama-server" >/dev/null && { echo "$(date -u +%FT%TZ) another server holds the GPU; not starting $TAG" >> $LOG; exit 0; }
  echo "$(date -u +%FT%TZ) chunk $TAG ($(wc -l < $f) problems)" >> $LOG
  IDS=$f PYTHON_ATTEMPTS=0 PORT=8852 bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" \
    --reference-python --specs-only --spec-samples 9 --spec-primer $PRIMER
  grep -E "spec_first: .*kept specification" t/out/laptop-runs/$TAG.route.log | tail -1 >> $LOG
  # the chunk's own server takes a moment to exit after laptop_route.sh kills it; wait for it before the next check
  for i in $(seq 1 30); do pgrep -f "[l]lama-server" >/dev/null || break; sleep 2; done
done
echo "$(date -u +%FT%TZ) all chunks done" >> $LOG
