#!/bin/bash
# One decode arm of the three-decode protocol (t/PREDICT-2026-10-22-seed-variance.md, Result): a model GGUF under the
# frozen route with --seed-offset N on the LAPTOP's GPU (the greedy calls replay from a seed cache, every sampled call
# draws afresh), the generation copied to the desktop and graded there on the CPU, the results copied back and paired
# per problem against the control. Generalised from t/recipes/decode_variance.sh (2026-10-22). Run as a user unit.
#   decode_arm.sh TAG GGUF IDENT SEED_OFFSET [SEED_CACHE]
#   env: BASELINE=v5-20261021-dev-desktop-r2  OUT=release/evidence/decode-<TAG>.json
set -u
TAG=${1:?tag}; GGUF=${2:?gguf}; IDENT=${3:?identity}; OFF=${4:?seed offset}; SEEDC=${5:-}
D=$HOME/Projects/dawnr; H=t@10.42.0.2; BASELINE=${BASELINE:-v5-20261021-dev-desktop-r2}
OUT=${OUT:-release/evidence/decode-$TAG.json}; LOG=$D/t/out/decode-arms.log
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $TAG: $*" | tee -a $LOG; }
log "generating on the laptop GPU (seed offset $OFF)"
SEED=$SEEDC bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" --seed-offset $OFF
grep -E "spec_first: " t/out/laptop-runs/$TAG.route.log | tail -1 | tee -a $LOG
log "copying to the desktop; grading on its cpu"
rsync -a --delete t/out/spec-experiment/$TAG/ $H:dawnr/t/out/spec-experiment/$TAG/ || { log "rsync failed"; exit 1; }
ssh -o ConnectTimeout=20 $H "systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/grade-$TAG.done; systemd-run --user --unit dawnr-grade-$TAG --collect -p WorkingDirectory=/home/t/dawnr bash t/recipes/v5_desktop_grade.sh $TAG"
until ssh -o ConnectTimeout=15 $H "test -f ~/v5-repair/grade-$TAG.done" 2>/dev/null; do sleep 120; done
rsync -a $H:~/v5-repair/proof-results/$TAG t/out/v5-repair-20261021/proof-results/ && rsync -a --exclude raw $H:dawnr/t/out/spec-experiment/$TAG/ t/out/spec-experiment/$TAG/
log "paired vs $BASELINE:"
python3 t/recipes/v7_local_pair.py --panel t/out/v6-20261018/dev-95.txt --baseline "$BASELINE:t/out/v5-repair-20261021/proof-results/$BASELINE" --candidate "$TAG:t/out/v5-repair-20261021/proof-results/$TAG" --out $OUT 2>&1 | tail -1 | cut -c1-400 | tee -a $LOG
log "arm complete"
