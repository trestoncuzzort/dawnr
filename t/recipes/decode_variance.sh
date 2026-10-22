#!/bin/bash
# The sampling-seed arm of t/PREDICT-2026-10-22-seed-variance.md: v5 (the installed shards) under the frozen route with
# --seed-offset 1000 on the LAPTOP's GPU, the greedy calls replayed from the control's cache, then the generation copied to
# the desktop and graded there on the CPU, then paired against the control. Run on the laptop as a user unit.
set -u
D=$HOME/Projects/dawnr; H=t@10.42.0.2; TAG=v5-20261022-seedoff1000
GGUF=$HOME/.local/share/dawnr/models/dawnr-student-00001-of-00003.gguf
IDENT="student-v5:d855000c3dffd9772da5a2f9dc238b41d7f8337d9bf58e578e5274ebb9566a4e:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $D/t/out/decode-variance.log; }
log "generating $TAG on the laptop GPU"
SEED=$D/t/out/v6-20261018/v5-dev/requests bash t/recipes/laptop_route.sh $TAG $GGUF "$IDENT" --seed-offset 1000
grep -E "spec_first: " t/out/laptop-runs/$TAG.route.log | tail -3 | tee -a $D/t/out/decode-variance.log
log "copying to the desktop; grading on its cpu"
rsync -a --delete t/out/spec-experiment/$TAG/ $H:dawnr/t/out/spec-experiment/$TAG/ || { log "rsync failed"; exit 1; }
ssh -o ConnectTimeout=20 $H "systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/grade-$TAG.done; systemd-run --user --unit dawnr-grade-$TAG --collect -p WorkingDirectory=/home/t/dawnr bash t/recipes/v5_desktop_grade.sh $TAG"
until ssh -o ConnectTimeout=15 $H "test -f ~/v5-repair/grade-$TAG.done" 2>/dev/null; do sleep 180; done
rsync -a $H:~/v5-repair/proof-results/$TAG t/out/v5-repair-20261021/proof-results/ && rsync -a --exclude raw $H:dawnr/t/out/spec-experiment/$TAG/ t/out/spec-experiment/$TAG/
log "paired:"
python3 t/recipes/v7_local_pair.py --panel t/out/v6-20261018/dev-95.txt --baseline "v5-20261021-dev-desktop-r2:t/out/v5-repair-20261021/proof-results/v5-20261021-dev-desktop-r2" --candidate "$TAG:t/out/v5-repair-20261021/proof-results/$TAG" --out release/evidence/v5-decode-seed-2026-10-22.json 2>&1 | tail -1 | cut -c1-400 | tee -a $D/t/out/decode-variance.log
log "decode variance arm complete"
