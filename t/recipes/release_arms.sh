#!/bin/bash
# The door's decodes and grades for one trained candidate, all on the laptop (internal/RELEASE-6.0-PLAN.md, section 3):
# three decodes (seed offsets 0, 1000, 2000) on the development 95 (pool v5) and on the wider reader's 145 (pool v7), on
# the laptop's GPU, then each arm graded natively by the laptop's seven kernels, one at a time (two seven-kernel grades
# at once can exhaust this 15 GB machine). A grade starts as soon as its decode exists, so grading overlaps decoding.
# Finished work is reused: a decoded arm is not decoded again and a graded one is not graded again.
#   release_arms.sh PFX GGUF IDENT          (launch as a user unit)
# Sources: t/recipes/model_arms.sh (the arms and tags), t/recipes/laptop_route.sh, t/recipes/v6-grade.sh.
set -u
PFX=${1:?prefix}; GGUF=${2:?gguf}; IDENT=${3:?identity}
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$PATH
D=$HOME/Projects/dawnr; cd $D || exit 1
LOG=$D/t/out/release-arms-$PFX.log
log() { echo "$(date -u +%FT%TZ) $PFX: $*" | tee -a $LOG; }
ARMS="dev:0 wider:0 dev:1000 wider:1000 dev:2000 wider:2000"
tagof() { local part=${1%%:*} off=${1##*:}
  if [ $part = dev ]; then if [ $off = 0 ]; then echo $PFX-dev; else echo $PFX-seedoff$off; fi; else echo $PFX-wider-off$off; fi; }
(
  for arm in $ARMS; do
    part=${arm%%:*}; TAG=$(tagof $arm)
    if [ $part = dev ]; then IDSF=t/out/v6-20261018/dev-95.txt; POOL=v5; else IDSF=t/out/v6-20261018/wider-145.txt; POOL=v7; fi
    OUT=t/out/v5-repair-20261021/proof-results/$TAG
    [ -s $OUT/GRADED ] && { log "$TAG already graded"; continue; }
    until [ -f t/out/laptop-runs/$TAG.done ]; do sleep 60; done
    [ "$(cat t/out/laptop-runs/$TAG.done)" = 0 ] || { log "$TAG decode failed; not graded"; continue; }
    rm -rf $OUT; mkdir -p $OUT
    rm -f t/out/spec-experiment/$TAG/kernels.md t/out/spec-experiment/$TAG/extract.json t/out/spec-experiment/$TAG/tests.json
    rm -rf t/out/spec-experiment/$TAG/tasks
    log "grading $TAG on the laptop"
    # one seven-kernel grade at a time on this machine, across every driver (the lock is shared)
    POOL=$POOL T_MIN_KERNELS=7 T_SPARK_JOBS=1 PYTHONUNBUFFERED=1 flock $D/t/out/.laptop-grade.lock bash t/recipes/v6-grade.sh $TAG $IDSF $OUT > t/out/lgrade-$TAG.log 2>&1
    log "$TAG graded rc=$?"
  done
  log "all grades done"
) &
GP=$!
for arm in $ARMS; do
  part=${arm%%:*}; off=${arm##*:}; TAG=$(tagof $arm)
  if [ $part = dev ]; then IDSF=t/out/v6-20261018/dev-95.txt; POOL=v5; SEEDC=t/out/laptop-runs/cache-$PFX-dev
  else IDSF=t/out/v6-20261018/wider-145.txt; POOL=v7; SEEDC=t/out/laptop-runs/cache-$PFX-wider-off0; fi
  if [ -f t/out/laptop-runs/$TAG.done ] && [ "$(cat t/out/laptop-runs/$TAG.done)" = 0 ]; then log "$TAG already decoded"; continue; fi
  log "decoding $TAG (seed offset $off)"
  # one model on the 8 GB card at a time, across every driver
  SEED=$SEEDC IDS=$IDSF POOL=$POOL flock $D/t/out/.laptop-gpu.lock bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" --seed-offset $off
  grep -E "spec_first: " t/out/laptop-runs/$TAG.route.log | tail -1 >> $LOG
done
log "all decodes done"
wait $GP
log "arms complete"
