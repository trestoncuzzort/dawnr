#!/bin/bash
# When the Modal training of v8 ends (t/recipes/v8_modal.py, volume dawnr-data:/v8-20261021): finalize on Modal (the
# finite-tensor check and the manifest of record), fetch the adapter to the laptop, stage it on the desktop, and start
# the desktop chain (t/recipes/v8_desktop_finish.sh: manifest, export, both development arms, grades, ceiling) as a
# user unit, then the primed teacher audition behind it, one GPU user at a time. Run on the laptop.
#   bash t/recipes/v8_from_modal.sh
# Sources: t/recipes/v7_modal.py (finalize), t/recipes/v8_desktop_finish.sh, modal volume get (modal.com/docs).
set -u
M=$HOME/scratch/venv-train/bin/modal; H=t@10.42.0.2; L=$HOME/.claude/jobs/d76813cf/tmp/v8-modal
ROWS_SHA=a279cc9a1b878865a447c61a67fc14250c39869c915e0cf7d3932ba6faf2cd03
cd "$(dirname "$0")/../.." || exit 1
mkdir -p $L
echo "--- finalize on Modal ---"
(cd t/recipes && timeout 1500 $M run v8_modal.py --mode finalize 2>&1 | tail -2 | cut -c1-300)
echo "--- fetch the adapter and the manifest ---"
rm -rf $L/adapter; timeout 1800 $M volume get dawnr-data /v8-20261021/adapter $L/ --force >/dev/null 2>&1 || { echo "volume get failed"; exit 1; }
[ -d $L/adapter ] || mv $L/v8-20261021/adapter $L/adapter 2>/dev/null
timeout 300 $M volume get dawnr-data /v8-20261021/manifest.json $L/manifest.json --force >/dev/null 2>&1
ls $L/adapter | tr '\n' ' '; echo
[ -f $L/adapter/adapter_model.safetensors ] || { echo "no adapter weights fetched"; exit 1; }
echo "--- stage on the desktop ---"
ssh -o ConnectTimeout=20 $H 'rm -rf ~/v8/adapter ~/v8/export; mkdir -p ~/v8' && rsync -a --exclude trainer $L/adapter/ $H:v8/adapter/ && rsync -a $L/manifest.json $H:v8/manifest-modal.json
ssh -o ConnectTimeout=20 $H "echo 0 > ~/v8/train.done; rm -f ~/v8/finish.done; systemctl --user reset-failed 2>/dev/null; for u in dawnr-v8-finish dawnr-teacher9b-primer; do systemctl --user stop \$u 2>/dev/null; done; systemd-run --user --unit dawnr-v8-finish --collect -p WorkingDirectory=/home/t/dawnr -E ROWS_SHA=$ROWS_SHA bash t/recipes/v8_desktop_finish.sh && systemd-run --user --unit dawnr-teacher9b-primer --collect -p WorkingDirectory=/home/t/dawnr bash -c 'until [ -f /home/t/v8/finish.done ]; do sleep 120; done; while pgrep -f \"[l]lama-server\" >/dev/null; do sleep 30; done; MODEL=teacher9b bash t/recipes/v5_desktop_repair.sh teacher9b-20261021-primer --python 10 --spec-samples 9 --specs-only --spec-primer /home/t/v5-repair/teacher-primer.md; PYTHONPATH=/home/t/dawnr/t python3 t/recipes/spec_ceiling.py --tag teacher9b-20261021-primer --ids-file /home/t/v7/dev-95.txt --n 200 --jobs 16 --out /home/t/v5-repair/teacher9b-primer-ceiling.json > /home/t/v5-repair/teacher9b-primer-ceiling.log 2>&1; touch /home/t/v5-repair/teacher9b-primer.done'; systemctl --user list-units --type=service --no-pager --no-legend 'dawnr-*' | cut -c1-60"
echo "--- desktop chain started; results land in ~/v8/finish.log on the desktop; then: bash t/recipes/v8_report.sh ---"
