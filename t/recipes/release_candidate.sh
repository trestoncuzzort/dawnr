#!/bin/bash
# One trained seed of a release candidate, from the desktop's adapter to the door's readings, everything after training on
# the laptop (internal/RELEASE-6.0-PLAN.md): wait for the desktop's run, fetch the adapter, check it is finite, write its
# manifest, export Q8_0 with the pinned converter, then the six arms (t/recipes/release_arms.sh) and the 20-candidate arm
# the ceiling instrument reads (t/recipes/spec_ceiling.py). Launch as a laptop user unit.
#   release_candidate.sh RUN PFX ROWS_SHA        e.g. release_candidate.sh r61a-s1 r61a-s1-20261024 2c2eff28...
# Sources: t/recipes/tandem_finish.sh (the fetch, manifest and export steps), t/PREDICT-2026-10-21-spec-ceiling.md.
set -u
RUN=${1:?run dir on the desktop}; PFX=${2:?tag prefix}; ROWS_SHA=${3:?rows sha}
H=${H:-tlab}; D=$HOME/Projects/dawnr; VENV=$HOME/scratch/venv-train; EXPORT=$D/t/out/$PFX-export; AD=$D/t/out/$PFX/adapter-final
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:$PATH
cd $D || exit 1
log() { echo "$(date -u +%FT%TZ) $PFX: $*" | tee -a $D/t/out/$PFX-handoff.log; }
until ssh -o ConnectTimeout=15 -o BatchMode=yes $H "test -f ~/$RUN/train.done && [ \"\$(cat ~/$RUN/train.done)\" = 0 ]" 2>/dev/null; do sleep 300; done
log "desktop training complete; fetching the adapter"
rm -rf $AD; mkdir -p $AD
rsync -a --exclude trainer $H:$RUN/adapter/ $AD/ || { log "rsync adapter failed"; exit 1; }
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
HF_HUB_OFFLINE=1 flock $D/t/out/.laptop-gpu.lock $VENV/bin/python t/recipes/v6_export.py --adapter $AD --manifest $D/t/out/$PFX/manifest.json \
  --llama-dir $HOME/scratch/llama.cpp-f1cee994 --out $EXPORT --device cpu --name dawnr-$PFX > $D/t/out/$PFX-export.log 2>&1 \
  || { log "export failed; see t/out/$PFX-export.log"; exit 1; }
SHA=$(python3 -c "import json;print(json.load(open('$EXPORT/export.json'))['output']['sha256'])")
IDENT="student-$PFX:${SHA}:llama-f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
log "export done sha=$SHA identity=$IDENT"
bash t/recipes/release_arms.sh $PFX $EXPORT/model-Q8_0.gguf "$IDENT"
log "the 20-candidate arm for the ceiling instrument"
SEED=$D/t/out/laptop-runs/cache-$PFX-dev PYTHON_ATTEMPTS=10 flock $D/t/out/.laptop-gpu.lock bash t/recipes/laptop_route.sh $PFX-oracle39 $EXPORT/model-Q8_0.gguf "$IDENT" --spec-samples 19 --oracle-gate
python3 t/recipes/spec_ceiling.py --tag $PFX-oracle39 --ids-file t/out/v6-20261018/dev-95.txt --n 200 --jobs 12 \
  --out $D/t/out/$PFX-ceiling.json > $D/t/out/$PFX-ceiling.log 2>&1
log "ceiling: $(tail -2 $D/t/out/$PFX-ceiling.log | tr '\n' ' ')"
log "the 33 given specifications"
bash t/recipes/spec33.sh $PFX $EXPORT/model-Q8_0.gguf > $D/t/out/$PFX-spec33.log 2>&1
log "spec33: $(tail -3 $D/t/out/$PFX-spec33.log | tr '\n' ' ')"
log "candidate seed complete"
