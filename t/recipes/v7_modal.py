"""Train the v7 decomposed-rows candidate on one Modal H100 at the exact v5 recipe.

    modal run --detach t/recipes/v7_modal.py --mode prepare
    modal run --detach t/recipes/v7_modal.py --mode train
    modal run --detach t/recipes/v7_modal.py --mode finalize

A fresh run from the registered base (no parent adapter), on the rows registered in
t/PREDICT-2026-10-19-decomposed-rows.md, uploaded to the data volume beforehand. The image, the
cached base snapshot, the volumes and the trainer digest are v6_modal.py's; the stage layout
(prepare asserts the inputs and records what the trainer will see, train refuses a changed input,
finalize writes the adapter manifest) is v6_modal_corrective.py's.
Sources: t/recipes/v6_modal.py; t/recipes/v6_modal_corrective.py;
https://modal.com/docs/examples/long-training
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import modal

if not modal.is_local():
    sys.path.insert(0, "/opt/dawnr/recipes")
from v6_modal import image as original_image, data, volumes, CACHE, MODEL, REVISION, TRAINER_SHA  # noqa: E402

RUN = Path("/data/v7-20261019")
INPUT = RUN / "inputs"
OUT = RUN / "adapter"
ROWS_SHA = "05f388b8d3ed763c7c5328e413885624b048c5e3d724ac28d9cefc87fd86159f"
ROWS = 4570
RECIPE_DIR = Path(__file__).resolve().parent if modal.is_local() else Path("/opt/dawnr/recipes")
image = original_image
for name in ("v6_modal.py",):
    image = image.add_local_file(str(RECIPE_DIR / name), "/opt/dawnr/recipes/" + name)
app = modal.App("dawnr-v7-decomposed", image=image)


def digest(path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@app.function(timeout=1800, cpu=4, memory=8192, volumes=volumes)
def prepare() -> dict:
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    import importlib.util

    rows_path = INPUT / "training-rows.jsonl"
    assert digest(rows_path) == ROWS_SHA, "training rows differ from the registration"
    build = json.loads((INPUT / "decomposition.json").read_text())
    assert build["output"]["sha256"] == ROWS_SHA and build["output"]["rows"] == ROWS
    audit = json.loads((INPUT / "audit.json").read_text())
    assert audit["rows"] == ROWS and not audit["flagged"] and not audit["findings"]
    assert digest("/opt/dawnr/student_sft.py") == TRAINER_SHA
    snapshot = Path(snapshot_download(MODEL, revision=REVISION, cache_dir=CACHE, local_files_only=True))
    assert snapshot.name == REVISION
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    spec = importlib.util.spec_from_file_location("v7_encoder", "/opt/dawnr/student_sft.py")
    trainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trainer)
    rows = trainer.load_rows(rows_path)
    assert len(rows) == ROWS
    used, encoded_hash = 0, hashlib.sha256()
    for row in rows:
        encoded = trainer.encode_row(tokenizer, row, 2**31 - 1)
        encoded_hash.update(json.dumps(encoded, sort_keys=True).encode() + b"\n")
        used += len(encoded["input_ids"]) <= 2845
    record = {"dataset_sha256": ROWS_SHA, "base": MODEL, "base_revision": REVISION, "snapshot": str(snapshot),
              "rows": len(rows), "rows_used": used, "dropped_too_long": len(rows) - used,
              "encoded_sha256": encoded_hash.hexdigest(),
              "steps": math.ceil(used / 16) * 5, "epochs": 5, "lr": 2e-4, "rank": 64, "alpha": 16,
              "dropout": 0.1, "seed": 1, "batch": 1, "grad_accum": 16, "max_len": 2845, "save_steps": 100,
              "trainer_sha256": TRAINER_SHA,
              "inputs_sha256": {name: digest(INPUT / name) for name in
                                ("training-rows.jsonl", "decomposition.json", "audit.json",
                                 "PREDICT-2026-10-19-decomposed-rows.md")}}
    path = INPUT / "prepared.json"
    if path.exists():
        assert json.loads(path.read_text()) == record, "inputs changed since the first preparation"
    path.write_text(json.dumps(record, indent=2) + "\n")
    data.commit()
    return record


@app.function(gpu="H100", timeout=8 * 3600, cpu=8, memory=32768, max_containers=1, volumes=volumes)
def train() -> dict:
    ready = json.loads((INPUT / "prepared.json").read_text())
    assert ready["dataset_sha256"] == ROWS_SHA
    for name, expected in ready["inputs_sha256"].items():
        assert digest(INPUT / name) == expected, f"input changed: {name}"
    assert digest("/opt/dawnr/student_sft.py") == ready["trainer_sha256"] == TRAINER_SHA
    assert not (OUT / "run.json").exists(), "training is already complete"
    checkpoints = sorted((OUT / "trainer").glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
    if checkpoints:
        required = ("adapter_config.json", "adapter_model.safetensors", "optimizer.pt",
                    "scheduler.pt", "rng_state.pth", "trainer_state.json", "training_args.bin")
        latest = checkpoints[-1]
        assert all((latest / name).is_file() and (latest / name).stat().st_size for name in required), \
            "latest checkpoint is incomplete; remove it before resuming"
        state = json.loads((latest / "trainer_state.json").read_text())
        assert state["max_steps"] == ready["steps"] and state["global_step"] == int(latest.name.split("-")[-1])
    command = ["python", "/opt/dawnr/student_sft.py", "--model", ready["snapshot"],
               "--sft", str(INPUT / "training-rows.jsonl"), "--sft-sha256", ROWS_SHA, "--out", str(OUT),
               "--rank", "64", "--alpha", "16", "--dropout", "0.1", "--lr", "2e-4",
               "--epochs", "5", "--max-len", "2845", "--seed", "1", "--batch", "1",
               "--grad-accum", "16", "--save-steps", "100", "--log-every", "10"]
    attempts = RUN / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    attempt = {"command": command, "started": time.time(), "gpu": "H100",
               "prepared_sha256": digest(INPUT / "prepared.json"),
               "resume_checkpoint": checkpoints[-1].name if checkpoints else None}
    (attempts / (str(time.time_ns()) + ".json")).write_text(json.dumps(attempt, indent=2) + "\n")
    data.commit()
    stop = threading.Event()

    def sync():
        while not stop.wait(120):
            data.commit()

    thread = threading.Thread(target=sync, daemon=True)
    thread.start()
    try:
        with (RUN / "train.log").open("a", buffering=1) as log:
            log.write(json.dumps(attempt) + "\n")
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=8 * 3600 - 600,
                                     env={**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1"})
        if process.returncode:
            raise RuntimeError("trainer failed; inspect train.log and the preserved checkpoints")
        record = json.loads((OUT / "run.json").read_text())
        assert record["steps"] == ready["steps"] and record["rows_used"] == ready["rows_used"]
        assert record["sft_sha256"] == ROWS_SHA and math.isfinite(record["train_loss"])
        return {"steps": record["steps"], "seconds": record["seconds"], "train_loss": record["train_loss"]}
    finally:
        stop.set()
        thread.join(timeout=5)
        data.commit()


@app.function(timeout=1200, cpu=4, memory=8192, volumes=volumes)
def finalize() -> dict:
    import torch
    from safetensors.torch import load_file

    ready = json.loads((INPUT / "prepared.json").read_text())
    record = json.loads((OUT / "run.json").read_text())
    assert record["steps"] == ready["steps"] and record["sft_sha256"] == ROWS_SHA
    tensors = load_file(str(OUT / "adapter_model.safetensors"))
    assert tensors and all(torch.isfinite(value).all() for value in tensors.values())
    manifest = {"kind": "v7-decomposed-rows-sft", "step": record["steps"], "data_sha256": ROWS_SHA,
                "prepared_sha256": digest(INPUT / "prepared.json"),
                "files": {str(path.relative_to(OUT)): digest(path) for path in sorted(OUT.rglob("*"))
                          if path.is_file() and "trainer" not in path.parts}}
    path = RUN / "manifest.json"
    if path.exists():
        assert json.loads(path.read_text()) == manifest
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    data.commit()
    return {"step": record["steps"], "train_loss": record["train_loss"],
            "adapter_sha256": manifest["files"]["adapter_model.safetensors"]}


@app.local_entrypoint()
def main(mode: str = "prepare"):
    functions = {"prepare": prepare, "train": train, "finalize": finalize}
    if mode not in functions:
        raise ValueError("mode must be prepare, train or finalize")
    call = functions[mode].spawn()
    print("Function call: " + call.object_id, flush=True)
    print(json.dumps(call.get()), flush=True)
