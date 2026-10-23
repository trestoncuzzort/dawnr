#!/bin/bash
# The protocol's arms for one trained model (t/PREDICT-2026-10-22-seed-variance.md, the protocol from v9): three decodes
# (seed offsets 0, 1000, 2000) on the development 95 (pool v5) and on the wider reader's 145 (pool v7), generated on the
# laptop's GPU and graded in the desktop container; the tandem's own dev arm (offset 0) is reused when present. The 9B
# teacher is stopped first and relaunched after. No pairing here: t/recipes/three_decode_report.py reads the joined
# parts (TAG-dev:DIR+TAG-wider-offN:DIR).
#   model_arms.sh PFX GGUF IDENT            e.g. model_arms.sh v9-20261022 t/out/v9-20261022-export/model-Q8_0.gguf "$IDENT"
# First run: v9-20261022 (t/out/model-arms.log), paused by the user on 2026-10-23 at 04:52Z with the two wider grades half
# done (internal/ROADMAP-LOG.md, 2026-10-23). Run the same command again: it skips what is generated and graded and redoes
# only the missing arms. H=tlab selects the tailnet route to the desktop when the cable address does not answer.
set -u
PFX=${1:?prefix}; GGUF=${2:?gguf}; IDENT=${3:?identity}
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$PATH   # a user unit's PATH lacks ~/.local/bin, where lean (and the aws CLI) live
D=$HOME/Projects/dawnr; H=${H:-t@10.42.0.2}; cd $D || exit 1
LOG=$D/t/out/model-arms.log; WIDER=t/out/v6-20261018/wider-145.txt
log() { echo "$(date -u +%FT%TZ) $PFX: $*" | tee -a $LOG; }
systemctl --user stop dawnr-teacher-train 2>/dev/null
for i in $(seq 1 40); do pgrep -f "[l]lama-server" >/dev/null || break; sleep 3; done
TAGS=""; LTAGS=""
for OFF in 0 1000 2000; do
  for PART in dev wider; do
    if [ $PART = dev ]; then TAG=$PFX-dev; [ $OFF != 0 ] && TAG=$PFX-seedoff$OFF; IDSF=t/out/v6-20261018/dev-95.txt; POOL=v5; SEEDC=t/out/laptop-runs/cache-$PFX-dev
    else TAG=$PFX-wider-off$OFF; IDSF=$WIDER; POOL=v7; SEEDC=t/out/laptop-runs/cache-$PFX-wider-off0; fi
    if [ -s t/out/spec-experiment/$TAG/spec_first.json ]; then log "$TAG already generated"; else
      log "generating $TAG (seed offset $OFF, $PART)"
      SEED=$SEEDC IDS=$IDSF POOL=$POOL bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" --seed-offset $OFF
      grep -E "spec_first: " t/out/laptop-runs/$TAG.route.log | tail -1 >> $LOG
    fi
    OUT=t/out/v5-repair-20261021/proof-results/$TAG
    if [ -s $OUT/GRADED ]; then log "$TAG already graded"; continue; fi
    if [ $PART = wider ]; then
      # the wider 145 (pool v7) are graded natively on the laptop's seven kernels, beside the desktop's dev grades
      rm -rf $OUT; mkdir -p $OUT; rm -f t/out/spec-experiment/$TAG/kernels.md t/out/spec-experiment/$TAG/extract.json t/out/spec-experiment/$TAG/tests.json; rm -rf t/out/spec-experiment/$TAG/tasks
      systemctl --user reset-failed 2>/dev/null
      systemd-run --user --unit dawnr-lgrade-$TAG --collect -p WorkingDirectory=$D -E PATH="$PATH" -E POOL=v7 -E T_MIN_KERNELS=7 -E T_SPARK_JOBS=1 -E PYTHONUNBUFFERED=1 /usr/bin/bash -c "bash t/recipes/v6-grade.sh $TAG $WIDER $OUT > t/out/lgrade-$TAG.log 2>&1; echo rc=\$? >> t/out/lgrade-$TAG.log" >> $LOG 2>&1
      LTAGS="${LTAGS:-} $TAG"; continue
    fi
    if [ "$(ssh -o ConnectTimeout=15 $H "cat ~/v5-repair/grade-$TAG.done 2>/dev/null")" = 0 ]; then
      # the tandem already graded this arm on the desktop: pull its artifacts, never push over them (a push with --delete
      # wiped v9's dev-arm grader files on 2026-10-23 01:10Z)
      rsync -a $H:~/v5-repair/proof-results/$TAG t/out/v5-repair-20261021/proof-results/ && rsync -a --exclude raw $H:dawnr/t/out/spec-experiment/$TAG/ t/out/spec-experiment/$TAG/
      log "$TAG pulled from the desktop's grade"; continue
    fi
    rsync -a t/out/spec-experiment/$TAG/ $H:dawnr/t/out/spec-experiment/$TAG/ || { log "rsync $TAG failed"; continue; }
    ssh -o ConnectTimeout=20 $H "systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/grade-$TAG.done; systemd-run --user --unit dawnr-grade-$TAG --collect -p WorkingDirectory=/home/t/dawnr bash t/recipes/v5_desktop_grade.sh $TAG" >> $LOG 2>&1
    TAGS="$TAGS $TAG"
  done
done
for i in $(seq 1 40); do pgrep -f "[l]lama-server" >/dev/null || break; sleep 3; done
STOP=$(( $(date +%s) + 6*3600 ))   # the teacher gets the card for six hours after the arms, whatever the clock says
{ systemctl --user reset-failed 2>/dev/null; systemd-run --user --unit dawnr-teacher-train --collect -p WorkingDirectory=$D -E STOP_AT=$STOP /usr/bin/bash t/recipes/teacher_train_specs.sh >/dev/null 2>&1 && log "teacher relaunched"; }
for TAG in $TAGS; do
  until ssh -o ConnectTimeout=15 $H "test -f ~/v5-repair/grade-$TAG.done" 2>/dev/null; do sleep 180; done
  rsync -a $H:~/v5-repair/proof-results/$TAG t/out/v5-repair-20261021/proof-results/ && rsync -a --exclude raw $H:dawnr/t/out/spec-experiment/$TAG/ t/out/spec-experiment/$TAG/
  log "$TAG graded: rc $(ssh -o ConnectTimeout=15 $H cat ~/v5-repair/grade-$TAG.done 2>/dev/null)"
done
for TAG in ${LTAGS:-}; do
  until [ -e t/out/v5-repair-20261021/proof-results/$TAG/GRADED ] || grep -q "^rc=" t/out/lgrade-$TAG.log 2>/dev/null; do sleep 120; done
  log "$TAG graded on the laptop: $(tail -1 t/out/lgrade-$TAG.log)"
done
log "all arms complete"
