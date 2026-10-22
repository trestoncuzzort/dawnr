#!/bin/bash
# The widened development panel's control arms (t/PREDICT-2026-10-22-seed-variance.md, the protocol from v9): v5 and
# its seed-2 twin, three decodes each (seed offsets 0, 1000, 2000), generated on the wider reader's 145 problems
# (t/out/v6-20261018/wider-145.txt) on the laptop's GPU and graded in the desktop container. The six generations run
# back to back (the 9B teacher is stopped first and relaunched after), the grades queue on the desktop as each lands.
# No pairing here: the readings merge with the dev-95 decodes per problem in the three-decode report.
set -u
D=$HOME/Projects/dawnr; H=t@10.42.0.2; cd $D || exit 1
LOG=$D/t/out/wider-arms.log; IDSF=t/out/v6-20261018/wider-145.txt
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
V5=$HOME/.local/share/dawnr/models/dawnr-student-00001-of-00003.gguf
V5ID=$(sed -n 's/.*identity=//p' t/out/laptop-runs/v5-20261022-seedoff1000.log | head -1)
S2=$D/t/out/v5s2-20261022-export/model-Q8_0.gguf
S2ID=$(sed -n 's/.*identity=//p' t/out/laptop-runs/v5s2-20261022-dev.log | head -1)
[ -n "$V5ID" ] && [ -n "$S2ID" ] || { log "identity missing"; exit 1; }
systemctl --user stop dawnr-teacher-train 2>/dev/null
for i in $(seq 1 40); do pgrep -f "[l]lama-server" >/dev/null || break; sleep 3; done
TAGS=""
for spec in "v5 $V5 $V5ID 0" "v5 $V5 $V5ID 1000" "v5 $V5 $V5ID 2000" "v5s2 $S2 $S2ID 0" "v5s2 $S2 $S2ID 1000" "v5s2 $S2 $S2ID 2000"; do
  set -- $spec; M=$1; GGUF=$2; IDENT=$3; OFF=$4; TAG=$M-20261022-wider-off$OFF
  if [ -s t/out/spec-experiment/$TAG/spec_first.json ]; then log "$TAG already generated"; else
    log "generating $TAG on the laptop GPU (145 problems, seed offset $OFF)"
    IDS=$IDSF POOL=v7 bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" --seed-offset $OFF   # wider problems: pool v7
    grep -E "spec_first: " t/out/laptop-runs/$TAG.route.log | tail -1 >> $LOG
  fi
  rsync -a --delete t/out/spec-experiment/$TAG/ $H:dawnr/t/out/spec-experiment/$TAG/ || { log "rsync $TAG failed"; continue; }
  ssh -o ConnectTimeout=20 $H "systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/grade-$TAG.done; systemd-run --user --unit dawnr-grade-$TAG --collect -p WorkingDirectory=/home/t/dawnr bash t/recipes/v5_desktop_grade.sh $TAG" >> $LOG 2>&1
  TAGS="$TAGS $TAG"
done
for i in $(seq 1 40); do pgrep -f "[l]lama-server" >/dev/null || break; sleep 3; done
STOP=$(date -u -d '2026-10-22 21:30' +%s)
[ "$(date +%s)" -lt "$STOP" ] && { systemctl --user reset-failed 2>/dev/null; systemd-run --user --unit dawnr-teacher-train --collect -p WorkingDirectory=$D -E STOP_AT=$STOP /usr/bin/bash t/recipes/teacher_train_specs.sh >/dev/null 2>&1 && log "teacher relaunched until 21:30Z"; }
for TAG in $TAGS; do
  until ssh -o ConnectTimeout=15 $H "test -f ~/v5-repair/grade-$TAG.done" 2>/dev/null; do sleep 180; done
  rsync -a $H:~/v5-repair/proof-results/$TAG t/out/v5-repair-20261021/proof-results/ && rsync -a --exclude raw $H:dawnr/t/out/spec-experiment/$TAG/ t/out/spec-experiment/$TAG/
  log "$TAG graded: rc $(ssh -o ConnectTimeout=15 $H cat ~/v5-repair/grade-$TAG.done 2>/dev/null)"
done
log "wider control arms complete"
