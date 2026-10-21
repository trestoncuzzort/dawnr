#!/bin/bash
# After the desktop finishes v8 (tlab:~/v8/train.done holds 0): fetch the adapter, EXPORT ON THE LAPTOP (CPU merge, pinned
# converter), GENERATE BOTH ARMS ON THE LAPTOP'S GPU (t/recipes/laptop_route.sh), copy them to the desktop, GRADE THERE ON THE
# CPU (kernel container) and run the ceiling instrument; then t/recipes/v8_report.sh pairs them. Run on the laptop as a user
# unit; it waits for the desktop. Sources: t/recipes/v6_export.py, t/recipes/laptop_route.sh, t/recipes/v5_desktop_grade.sh.
set -u
H=t@10.42.0.2; D=$HOME/Projects/dawnr; VENV=$HOME/scratch/venv-train; EXPORT=$D/t/out/v8-export; AD=$D/t/out/v8-20261021/adapter-final
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $D/t/out/v8-handoff.log; }
until ssh -o ConnectTimeout=15 $H 'test -f ~/v8/train.done && [ "$(cat ~/v8/train.done)" = 0 ]' 2>/dev/null; do sleep 300; done
log "desktop training complete; fetching the adapter"
rm -rf $AD; mkdir -p $AD
rsync -a --exclude trainer $H:v8/adapter/ $AD/ || { log "rsync adapter failed"; exit 1; }
ssh -o ConnectTimeout=15 $H 'systemctl --user disable dawnr-v8-train.service >/dev/null 2>&1; true'
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
manifest = {"kind": "v8-self-distilled-specs-sft", "step": run.get("steps"), "data_sha256": "a279cc9a1b878865a447c61a67fc14250c39869c915e0cf7d3932ba6faf2cd03",
            "files": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}}
pathlib.Path("$D/t/out/v8-20261021/manifest.json").write_text(json.dumps(manifest, indent=2) + "\\n")
print("manifest", manifest["step"], manifest["files"]["adapter_model.safetensors"][:16])
PY
log "export on the laptop (cpu merge, pinned converter)"
rm -rf $EXPORT
HF_HUB_OFFLINE=1 $VENV/bin/python t/recipes/v6_export.py --adapter $AD --manifest $D/t/out/v8-20261021/manifest.json \
  --llama-dir $HOME/scratch/llama.cpp-f1cee994 --out $EXPORT --device cpu --name dawnr-v8 > $D/t/out/v8-export.log 2>&1 \
  || { log "export failed; see t/out/v8-export.log"; exit 1; }
SHA=$(python3 -c "import json;print(json.load(open('$EXPORT/export.json'))['output']['sha256'])")
IDENT="student-v8:${SHA}:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
log "export done sha=$SHA; generating the frozen-route arm on the laptop GPU"
bash t/recipes/laptop_route.sh v8-20261021-dev $EXPORT/model-Q8_0.gguf "$IDENT"
log "generating the 39-call oracle arm on the laptop GPU"
SEED=$D/t/out/laptop-runs/cache-v8-20261021-dev PYTHON_ATTEMPTS=10 bash t/recipes/laptop_route.sh v8-20261021-oracle39 $EXPORT/model-Q8_0.gguf "$IDENT" --spec-samples 19 --oracle-gate
log "copying the generations to the desktop; grading there on the cpu"
for tag in v8-20261021-dev v8-20261021-oracle39; do
  rsync -a --delete t/out/spec-experiment/$tag/ $H:dawnr/t/out/spec-experiment/$tag/ || { log "rsync $tag failed"; exit 1; }
done
ssh -o ConnectTimeout=20 $H 'systemctl --user reset-failed 2>/dev/null; rm -f ~/v5-repair/v8-grades.done; systemd-run --user --unit dawnr-v8-grades --collect -p WorkingDirectory=/home/t/dawnr bash -c "bash t/recipes/v5_desktop_grade.sh v8-20261021-dev; bash t/recipes/v5_desktop_grade.sh v8-20261021-oracle39; PYTHONPATH=/home/t/dawnr/t python3 t/recipes/spec_ceiling.py --tag v8-20261021-oracle39 --ids-file /home/t/v7/dev-95.txt --n 200 --jobs 16 --out /home/t/v5-repair/v8-ceiling.json > /home/t/v5-repair/v8-ceiling.log 2>&1; touch /home/t/v5-repair/v8-grades.done"'
until ssh -o ConnectTimeout=15 $H 'test -f ~/v5-repair/v8-grades.done' 2>/dev/null; do sleep 300; done
log "desktop grades done; pairing"
bash t/recipes/v8_report.sh 2>&1 | tee -a $D/t/out/v8-handoff.log
log "v8 tandem finish complete"
