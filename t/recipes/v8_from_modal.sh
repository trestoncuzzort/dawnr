#!/bin/bash
# When the Modal training of v8 ends (t/recipes/v8_modal.py, volume dawnr-data:/v8-20261021): finalize on Modal, fetch
# the adapter, EXPORT ON THE LAPTOP (CPU merge, the pinned converter), GENERATE BOTH ARMS ON THE LAPTOP'S GPU
# (t/recipes/laptop_route.sh), copy the generations to the desktop and GRADE THERE ON THE CPU (the kernel container),
# then the ceiling instrument on the desktop CPU. The desktop's 4080 is not loaded (the user, 2026-10-21: the laptop's
# card and the desktop's in tandem; the 4080 drops under load from a physical fault). Run on the laptop as a user unit:
#   systemd-run --user --unit dawnr-v8-handoff --collect -p WorkingDirectory=/home/t/Projects/dawnr bash t/recipes/v8_from_modal.sh
# Sources: t/recipes/v7_modal.py (finalize), t/recipes/v6_export.py, t/recipes/laptop_route.sh, t/recipes/v5_desktop_grade.sh.
set -u
M=$HOME/scratch/venv-train/bin/modal; H=t@10.42.0.2; L=$HOME/.claude/jobs/d76813cf/tmp/v8-modal; D=$HOME/Projects/dawnr
VENV=$HOME/scratch/venv-train; EXPORT=$D/t/out/v8-export
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $D/t/out/v8-handoff.log; }
log "finalize on Modal"
(cd t/recipes && timeout 1500 $M run v8_modal.py --mode finalize 2>&1 | tail -2 | cut -c1-300 | tee -a $D/t/out/v8-handoff.log)
log "fetch the adapter"
rm -rf $L/adapter $L/v8-20261021; mkdir -p $L
timeout 1800 $M volume get dawnr-data /v8-20261021/adapter $L/ --force >/dev/null 2>&1 || { log "volume get failed"; exit 1; }
[ -d $L/adapter ] || mv $L/v8-20261021/adapter $L/adapter 2>/dev/null
timeout 300 $M volume get dawnr-data /v8-20261021/manifest.json $L/manifest.json --force >/dev/null 2>&1
[ -f $L/adapter/adapter_model.safetensors ] || { log "no adapter weights fetched"; exit 1; }
log "export on the laptop (cpu merge, pinned converter)"
rm -rf $EXPORT
HF_HUB_OFFLINE=1 $VENV/bin/python t/recipes/v6_export.py --adapter $L/adapter --manifest $L/manifest.json \
  --llama-dir $HOME/scratch/llama.cpp-f1cee994 --out $EXPORT --device cpu --name dawnr-v8 > $D/t/out/v8-export.log 2>&1 \
  || { log "export failed; see t/out/v8-export.log"; exit 1; }
SHA=$(python3 -c "import json;print(json.load(open('$EXPORT/export.json'))['output']['sha256'])")
IDENT="student-v8:${SHA}:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
log "export done sha=$SHA"
log "generate the frozen-route arm on the laptop GPU"
bash t/recipes/laptop_route.sh v8-20261021-dev $EXPORT/model-Q8_0.gguf "$IDENT"
log "generate the 39-call oracle arm on the laptop GPU"
SEED=$D/t/out/laptop-runs/cache-v8-20261021-dev PYTHON_ATTEMPTS=10 bash t/recipes/laptop_route.sh v8-20261021-oracle39 $EXPORT/model-Q8_0.gguf "$IDENT" --spec-samples 19 --oracle-gate
log "copy the generations to the desktop and grade there (cpu)"
for tag in v8-20261021-dev v8-20261021-oracle39; do
  rsync -a --delete t/out/spec-experiment/$tag/ $H:dawnr/t/out/spec-experiment/$tag/ || { log "rsync $tag failed"; exit 1; }
done
ssh -o ConnectTimeout=20 $H 'systemctl --user reset-failed 2>/dev/null; systemd-run --user --unit dawnr-v8-grades --collect -p WorkingDirectory=/home/t/dawnr bash -c "bash t/recipes/v5_desktop_grade.sh v8-20261021-dev; bash t/recipes/v5_desktop_grade.sh v8-20261021-oracle39; PYTHONPATH=/home/t/dawnr/t python3 t/recipes/spec_ceiling.py --tag v8-20261021-oracle39 --ids-file /home/t/v7/dev-95.txt --n 200 --jobs 16 --out /home/t/v5-repair/v8-ceiling.json > /home/t/v5-repair/v8-ceiling.log 2>&1; touch /home/t/v5-repair/v8-grades.done"'
log "desktop grades queued (sentinel ~/v5-repair/v8-grades.done on the desktop); then: bash t/recipes/v8_report.sh"
