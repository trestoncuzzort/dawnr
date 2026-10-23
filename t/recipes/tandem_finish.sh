#!/bin/bash
# Generalised from v8_tandem_finish.sh (2026-10-22; 15:35Z the grade and done-file commands were single-quoted, so $PFX reached the desktop empty and v5s2 graded nothing): usage tandem_finish.sh RUN TAGPREFIX ROWS_SHA. After the desktop finishes a run (tlab:~/$RUN/train.done holds 0): fetch the adapter, EXPORT ON THE LAPTOP (CPU merge, pinned
# converter), GENERATE BOTH ARMS ON THE LAPTOP'S GPU (t/recipes/laptop_route.sh), copy them to the desktop, GRADE THERE ON THE
# CPU (kernel container) and run the ceiling instrument; then t/recipes/v8_report.sh pairs them. Run on the laptop as a user
# unit; it waits for the desktop. Sources: t/recipes/v6_export.py, t/recipes/laptop_route.sh, t/recipes/v5_desktop_grade.sh.
set -u
RUN=${1:?run dir on the desktop, e.g. v5s2}; PFX=${2:?tag prefix, e.g. v5s2-20261022}; ROWS_SHA=${3:?rows sha}
H=${H:-t@10.42.0.2}; D=$HOME/Projects/dawnr; VENV=$HOME/scratch/venv-train; EXPORT=$D/t/out/$PFX-export; AD=$D/t/out/$PFX/adapter-final
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $D/t/out/$PFX-handoff.log; }
until ssh -o ConnectTimeout=15 $H "test -f ~/$RUN/train.done && [ \"\$(cat ~/$RUN/train.done)\" = 0 ]" 2>/dev/null; do sleep 300; done
log "desktop training complete; fetching the adapter"
rm -rf $AD; mkdir -p $AD
rsync -a --exclude trainer $H:$RUN/adapter/ $AD/ || { log "rsync adapter failed"; exit 1; }
ssh -o ConnectTimeout=15 $H "systemctl --user disable dawnr-$RUN-train.service >/dev/null 2>&1; true"
$VENV/bin/python - <<PY || { log "manifest failed"; exit 1; }
import hashlib, json, pathlib, torch
from safetensors.torch import load_file
out = pathlib.Path("$AD")
tensors = load_file(str(out / "adapter_model.safetensors"))
assert tensors and all(torch.isfinite(v).all() for v in tensors.values()), "non-finite adapter"
def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
run = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
manifest = {"kind": "$PFX-sft", "step": run.get("steps"), "data_sha256": "$ROWS_SHA",
            "files": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}}
pathlib.Path("$D/t/out/$PFX/manifest.json").write_text(json.dumps(manifest, indent=2) + "\\n")
print("manifest", manifest["step"], manifest["files"]["adapter_model.safetensors"][:16])
PY
log "export on the laptop (cpu merge, pinned converter)"
rm -rf $EXPORT
HF_HUB_OFFLINE=1 $VENV/bin/python t/recipes/v6_export.py --adapter $AD --manifest $D/t/out/$PFX/manifest.json \
  --llama-dir $HOME/scratch/llama.cpp-f1cee994 --out $EXPORT --device cpu --name dawnr-$PFX > $D/t/out/$PFX-export.log 2>&1 \
  || { log "export failed; see t/out/$PFX-export.log"; exit 1; }
SHA=$(python3 -c "import json;print(json.load(open('$EXPORT/export.json'))['output']['sha256'])")
IDENT="student-$PFX:${SHA}:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
log "export done sha=$SHA; generating the frozen-route arm on the laptop GPU"
bash t/recipes/laptop_route.sh $PFX-dev $EXPORT/model-Q8_0.gguf "$IDENT"
log "generating the 39-call oracle arm on the laptop GPU"
SEED=$D/t/out/laptop-runs/cache-$PFX-dev PYTHON_ATTEMPTS=10 bash t/recipes/laptop_route.sh $PFX-oracle39 $EXPORT/model-Q8_0.gguf "$IDENT" --spec-samples 19 --oracle-gate
log "copying the generations to the desktop; grading there on the cpu"
for tag in $PFX-dev $PFX-oracle39; do
  rsync -a --delete t/out/spec-experiment/$tag/ $H:dawnr/t/out/spec-experiment/$tag/ || { log "rsync $tag failed"; exit 1; }
done
ssh -o ConnectTimeout=20 $H "systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/$PFX-grades.done; systemd-run --user --unit dawnr-$PFX-grades --collect -p WorkingDirectory=/home/t/dawnr bash -c \"bash t/recipes/v5_desktop_grade.sh $PFX-dev; bash t/recipes/v5_desktop_grade.sh $PFX-oracle39; PYTHONPATH=/home/t/dawnr/t python3 t/recipes/spec_ceiling.py --tag $PFX-oracle39 --ids-file /home/t/v7/dev-95.txt --n 200 --jobs 16 --out /home/t/v5-repair/$PFX-ceiling.json > /home/t/v5-repair/$PFX-ceiling.log 2>&1; touch /home/t/v5-repair/$PFX-grades.done\""
until ssh -o ConnectTimeout=15 $H "test -f ~/v5-repair/$PFX-grades.done" 2>/dev/null; do sleep 300; done
log "desktop grades done; pairing"
echo "pair with v7_local_pair.py against the controls" 2>&1 | tee -a $D/t/out/$PFX-handoff.log
log "$PFX tandem finish complete"
