"""Resume the registered v6 checkpoint on one Modal GPU without changing its trainer.

    modal run --detach t/recipes/v6_modal.py --mode prepare
    modal run --detach t/recipes/v6_modal.py --mode train

Checkpoint transport is separate. Training refuses an absent or mismatched checkpoint.
Sources: locallm/cloud_train.py; modal.com/docs/examples/long-training;
huggingface.co/docs/transformers/v5.0.0/trainer. Registration: ../PREDICT-2026-10-18-v6.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import modal

TRAINER_SOURCE = (Path(__file__).resolve().parents[2] / "t/student_sft.py"
                  if modal.is_local() else Path("/opt/dawnr/student_sft.py"))
MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
ROWS_SHA = "e14f766f06299d589d9a6e3293f6bf3e3f06ffac026433e2fdeff1c04294af80"
TRAINER_SHA = "e43c27df1ee1e796b1799d38a16e0c5725dd09df762be3fabb2940ad8cb4a46f"
GPU = os.environ.get("DAWNR_GPU", "A100-80GB")
TIMEOUT_S = int(os.environ.get("DAWNR_TIMEOUT_S", str(4 * 3600)))
RUN = Path("/data/v6-20261018")
CACHE = "/models/v6-20261018/hub"
data = modal.Volume.from_name("dawnr-data")
models = modal.Volume.from_name("dawnr-hf-cache")
image = (modal.Image.debian_slim(python_version="3.10")
         .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu129")
         .pip_install("transformers==5.20.1", "peft==0.21.2", "bitsandbytes==0.50.2",
                      "accelerate==1.15.0", "jinja2==3.1.6", "numpy==2.2.6",
                      "safetensors==0.8.0", "huggingface-hub==2.2.0")
         .env({"HF_HUB_CACHE": CACHE, "OMP_NUM_THREADS": "8", "DAWNR_GPU": GPU,
               "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
         .add_local_file(str(TRAINER_SOURCE), "/opt/dawnr/student_sft.py"))
app = modal.App("dawnr-v6-resume", image=image)
volumes = {"/data": data, "/models": models}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@app.function(timeout=1800, cpu=4, memory=8192, volumes=volumes)
def prepare() -> dict:
    from huggingface_hub import snapshot_download
    import importlib.metadata as metadata

    snapshot = snapshot_download(MODEL, revision=REVISION, cache_dir=CACHE)
    record = {"model": MODEL, "revision": REVISION, "snapshot": snapshot,
              "packages": {name: metadata.version(name) for name in
                           ("torch", "transformers", "peft", "bitsandbytes", "accelerate")}}
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "model-source.json").write_text(json.dumps(record, indent=2) + "\n")
    models.commit()
    data.commit()
    print(json.dumps(record), flush=True)
    return record


@app.function(timeout=900, cpu=2, memory=4096, volumes=volumes)
def checkpoint() -> dict:
    """Register the latest complete checkpoint after a stopped training call.

    The controller must establish that the previous call is terminal first. This
    does not start training or replace completed artifacts. Incomplete directories
    are preserved outside the Trainer's automatic checkpoint selection.
    """
    out = RUN / "adapter"
    if (out / "run.json").exists():
        raise RuntimeError("training is complete; export it instead of resuming")
    prior = json.loads((RUN / "resume.json").read_text())
    if prior["trainer_sha256"] != TRAINER_SHA or prior["data_sha256"] != ROWS_SHA:
        raise RuntimeError("previous training call does not match this recipe")
    if digest(out / "training-rows.jsonl") != ROWS_SHA:
        raise RuntimeError("frozen training data changed")
    required = {"adapter_config.json", "adapter_model.safetensors", "optimizer.pt",
                "scheduler.pt", "rng_state.pth", "trainer_state.json", "training_args.bin"}
    candidates = sorted((out / "trainer").glob("checkpoint-*"),
                        key=lambda p: int(p.name.split("-")[-1]), reverse=True)
    skipped = []
    for candidate in candidates:
        if not all((candidate / name).is_file() and (candidate / name).stat().st_size for name in required):
            skipped.append(candidate.name)
            continue
        state = json.loads((candidate / "trainer_state.json").read_text())
        step = int(candidate.name.split("-")[-1])
        if state["global_step"] != step or state["max_steps"] != 1275 or step < prior["from_step"]:
            raise RuntimeError("checkpoint state does not belong to the registered continuation")
        files = [out / "training-rows.jsonl", out / "training-data.json"]
        files += sorted(p for p in candidate.rglob("*") if p.is_file())
        manifest = {"checkpoint": candidate.name, "step": step, "skipped_incomplete": skipped,
                    "files": {str(p.relative_to(out)): digest(p) for p in files}}
        if skipped:
            quarantine = RUN / "incomplete-checkpoints"
            quarantine.mkdir(exist_ok=True)
            for name in skipped:
                (out / "trainer" / name).rename(quarantine / f"{name}-{time.time_ns()}")
        history = RUN / "checkpoint-manifests"
        history.mkdir(exist_ok=True)
        encoded = json.dumps(manifest, indent=2) + "\n"
        (history / f"{step}.json").write_text(encoded)
        temporary = RUN / "checkpoint-manifest.json.tmp"
        temporary.write_text(encoded)
        temporary.replace(RUN / "checkpoint-manifest.json")
        data.commit()
        return {"step": step, "files": len(files), "skipped_incomplete": skipped}
    raise RuntimeError("no complete checkpoint is available")


@app.function(gpu="H100", timeout=900, cpu=8, memory=32768, volumes=volumes)
def benchmark_h100() -> dict:
    """Ten updates from the preserved step-300 state; never used as a release candidate."""
    import shutil
    import tempfile
    original = RUN / "adapter"
    prior = json.loads((RUN / "resume.json").read_text())
    if prior["from_step"] != 300 or prior["data_sha256"] != ROWS_SHA:
        raise RuntimeError("the benchmark requires the unchanged step-300 experiment")
    with tempfile.TemporaryDirectory(prefix="v6-speed-") as temporary:
        out = Path(temporary) / "adapter"
        shutil.copytree(original / "trainer/checkpoint-300", out / "trainer/checkpoint-300")
        for name in ("training-rows.jsonl", "training-data.json"):
            shutil.copy2(original / name, out / name)
        command = list(prior["command"])
        command[command.index("--out") + 1] = str(out)
        command[command.index("--log-every") + 1] = "1"
        command += ["--max-steps", "310"]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=800, env={**os.environ, "HF_HUB_OFFLINE": "1"})
        (RUN / "benchmark-h100.log").write_text(result.stdout)
        data.commit()
        if result.returncode:
            raise RuntimeError(f"benchmark failed: {result.returncode}; see benchmark-h100.log")
        run = json.loads((out / "run.json").read_text())
        if run["steps"] != 310:
            raise RuntimeError("benchmark did not finish exactly ten resumed updates")
        record = {"from_step": 300, "to_step": 310, "seconds": run["seconds"],
                  "seconds_per_update": run["seconds"] / 10, "train_loss": run["train_loss"],
                  "gpu": subprocess.check_output(["nvidia-smi", "--query-gpu=name",
                                                  "--format=csv,noheader"], text=True).strip()}
        (RUN / "benchmark-h100.json").write_text(json.dumps(record, indent=2) + "\n")
        data.commit()
        return record


@app.function(gpu=GPU, timeout=TIMEOUT_S + 300, cpu=8, memory=32768,
              max_containers=1, volumes=volumes)
def train() -> dict:
    model = json.loads((RUN / "model-source.json").read_text())
    if model["model"] != MODEL or model["revision"] != REVISION:
        raise RuntimeError("base model differs from the registered checkpoint")
    out = RUN / "adapter"
    manifest = json.loads((RUN / "checkpoint-manifest.json").read_text())
    for name, expected in manifest["files"].items():
        path = out / name
        if path.is_absolute() and out not in path.parents:
            raise RuntimeError("checkpoint manifest path is outside the adapter directory")
        if ".." in Path(name).parts or digest(path) != expected:
            raise RuntimeError(f"checkpoint digest mismatch: {name}")
    state = json.loads((out / "trainer" / manifest["checkpoint"] / "trainer_state.json").read_text())
    if state["global_step"] != manifest["step"] or state["max_steps"] != 1275:
        raise RuntimeError("checkpoint step count differs from the transferred state")
    latest = max((out / "trainer").glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
    if latest.name != manifest["checkpoint"]:
        raise RuntimeError("register the latest complete checkpoint before resuming")
    rows = out / "training-rows.jsonl"
    trainer = Path("/opt/dawnr/student_sft.py")
    if digest(rows) != ROWS_SHA or digest(trainer) != TRAINER_SHA:
        raise RuntimeError("training data or trainer differs from the GCP run")
    if (out / "run.json").exists():
        raise RuntimeError("training has already completed; do not run it twice")
    command = ["python", str(trainer), "--model", model["snapshot"],
               "--sft", str(rows), "--sft-sha256", ROWS_SHA, "--out", str(out),
               "--rank", "64", "--alpha", "16", "--dropout", "0.1", "--lr", "2e-4",
               "--epochs", "5", "--max-len", "2845", "--seed", "1", "--batch", "1",
               "--grad-accum", "16", "--save-steps", "100", "--log-every", "10"]
    started = time.time()
    receipt = {"gpu": GPU, "from_step": state["global_step"], "started": started,
               "command": command, "trainer_sha256": TRAINER_SHA, "data_sha256": ROWS_SHA}
    attempts = RUN / "attempts"
    attempts.mkdir(exist_ok=True)
    encoded = json.dumps(receipt, indent=2) + "\n"
    (attempts / f"from-{state['global_step']}-{int(started)}.json").write_text(encoded)
    (RUN / "resume.json").write_text(encoded)
    data.commit()
    stop = threading.Event()

    def commit_checkpoints():
        while not stop.wait(120):
            data.commit()

    thread = threading.Thread(target=commit_checkpoints, daemon=True)
    thread.start()
    try:
        with (RUN / "train.log").open("a", buffering=1) as log:
            log.write(f"resume step={state['global_step']} gpu={GPU}\n")
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, env={**os.environ, "HF_HUB_OFFLINE": "1"}) as proc:
                for line in proc.stdout:
                    log.write(line)
                    print(line, end="", flush=True)
                if proc.wait() != 0:
                    raise RuntimeError(f"student_sft exited {proc.returncode}")
        result = json.loads((out / "run.json").read_text())
        if result["steps"] != 1275 or not (out / "adapter_model.safetensors").is_file():
            raise RuntimeError("training returned without the completed adapter")
        return {"steps": result["steps"], "seconds_this_call": time.time() - started}
    finally:
        stop.set()
        thread.join(timeout=5)
        data.commit()


@app.local_entrypoint()
def main(mode: str = "prepare"):
    modes = {"prepare": prepare, "checkpoint": checkpoint, "train": train,
             "benchmark-h100": benchmark_h100}
    if mode not in modes:
        raise ValueError("mode must be prepare, checkpoint, train, or benchmark-h100")
    call = modes[mode].spawn()
    print(f"Function call: {call.object_id}", flush=True)
    print(json.dumps(call.get()), flush=True)
