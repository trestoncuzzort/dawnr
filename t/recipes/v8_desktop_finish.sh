#!/bin/bash
# After v8 trains on the desktop (t/recipes/v8_desktop_train.sh): the adapter manifest, the pinned export
# (t/recipes/v6_export.py, converter ~/llama.cpp-f1cee994 at f1cee994), then the development arms under the frozen
# 17-call route and the 39-call oracle route (t/recipes/v5_desktop_repair.sh MODEL=v8), and both grades in the kernel
# container. Launch as a user unit; sentinel ~/v8/finish.done. Sources: t/recipes/v7_modal.py finalize (the manifest's
# shape), t/recipes/v6_export.py, t/PREDICT-2026-10-21-v8-spec-rows.md.
set -u
H=/home/t; D=$H/dawnr; V=$H/v8; VENV=$H/venv-train
cd $D || exit 1
rm -f $V/finish.done
log() { echo "$(date -u +%FT%TZ) $*" >> $V/finish.log; }
log "start"
[ -f $V/train.done ] && [ "$(cat $V/train.done)" = 0 ] || { log "training did not finish cleanly"; echo 93 > $V/finish.done; exit 1; }
$VENV/bin/python - <<PY || { log "manifest failed"; echo 94 > $V/finish.done; exit 1; }
import hashlib, json, pathlib, torch
from safetensors.torch import load_file
out = pathlib.Path("$V/adapter")
tensors = load_file(str(out / "adapter_model.safetensors"))
assert tensors and all(torch.isfinite(v).all() for v in tensors.values()), "adapter has non-finite values"
def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
run = json.loads((out / "run.json").read_text()) if (out / "run.json").exists() else {}
manifest = {"kind": "v8-self-distilled-specs-sft", "step": run.get("steps"), "data_sha256": "${ROWS_SHA:?}",
            "files": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file() and "trainer" not in p.parts}}
pathlib.Path("$V/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("manifest", manifest["files"]["adapter_model.safetensors"][:16])
PY
log "manifest written"
export HF_HUB_OFFLINE=1 HF_HUB_CACHE=$H/hf-cache PYTHONUNBUFFERED=1
rm -rf $V/export
$VENV/bin/python t/recipes/v6_export.py --adapter $V/adapter --manifest $V/manifest.json --llama-dir $H/llama.cpp-f1cee994 \
  --out $V/export --device cuda --name dawnr-v8 > $V/export.log 2>&1 || { log "export failed rc=$?"; echo 95 > $V/finish.done; exit 1; }
log "export done: $(ls $V/export)"
MODEL=v8 bash t/recipes/v5_desktop_repair.sh v8-20261021-dev
MODEL=v8 bash t/recipes/v5_desktop_repair.sh v8-20261021-oracle39 --python 10 --spec-samples 19 --oracle-gate
log "generation done"
bash t/recipes/v5_desktop_grade.sh v8-20261021-dev
bash t/recipes/v5_desktop_grade.sh v8-20261021-oracle39
PYTHONPATH=$D/t python3 t/recipes/spec_ceiling.py --tag v8-20261021-oracle39 --ids-file $H/v7/dev-95.txt --n 200 --jobs 16 \
  --out $H/v5-repair/v8-ceiling.json > $H/v5-repair/v8-ceiling.log 2>&1
log "grades done"
echo 0 > $V/finish.done
