"""A pretraining arm on a rented GPU (Modal), the trainer and its command unchanged.

The English pilot's arms are commands (internal/PRETRAIN-DAWNR-GENERAL.md 7.4; the
registration, t/PREDICT-2026-09-29-dawnr-english-pilot.md): `train_distributed.py` under
torchrun with the r12 sweep's recipe. This launcher runs that same command inside a Modal
Function on one GPU (docs: modal.com/docs/guide/gpu, modal.com/docs/guide/volumes) with a
Volume mounted at /data holding the corpus, the tokenizer and every run directory, so the
run's own checkpoints (`--save-every`, resumed with `--resume` and the RNG restored on the
CPU) persist across a preempted or killed container. The judgement stays on the desktop:
`modal volume get dawnr-data runs/<name> <local dir>` brings the run directory back and the
pilot's launcher judges it the way it judges every arm.

    modal volume put dawnr-data <tokenizer.json> tokenizer.json
    modal volume put dawnr-data <corpus.txt> corpus/train.txt
    DAWNR_GPU=H100 modal run --detach locallm/cloud_train.py --steps 63111 --out runs/arm-c-matched-code

Research only (release.py names it so): it imports modal, which the shipped app never does.
Nothing here names a person, a machine or an account; the workspace comes from ~/.modal.toml.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import modal

GPU = os.environ.get("DAWNR_GPU", "H100")
HERE = Path(__file__).resolve().parent

volume = modal.Volume.from_name("dawnr-data", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch", "numpy", "tokenizers")
         .add_local_dir(str(HERE), remote_path="/root/locallm",
                        ignore=["__pycache__", "*.pyc", "fixtures", "test_*", "dawnr_learning", "dawnr_harness",
                                "included-model", "*.md"]))
app = modal.App("dawnr-pretrain", image=image)

# The registered recipe, verbatim from the pilot's launcher (paths aside).
RECIPE = ["--tokenizer-file", "/data/tokenizer.json", "--architecture", "gpt", "--preset", "core-medium",
          "--vocab-size", "8192", "--block-size", "2048", "--n-layer", "12", "--n-head", "12", "--n-embd", "768",
          "--gradient-checkpointing", "--batch-size", "8", "--grad-accum", "1", "--dropout", "0.0",
          "--lr", "0.001", "--weight-decay", "0.8", "--warmup-steps", "560", "--seed", "1337",
          "--deterministic", "--bf16"]


@app.function(gpu=GPU, timeout=12 * 3600, volumes={"/data": volume}, cpu=4.0, memory=24576)
def train(steps: int, out: str, data: str = "corpus/train.txt", save_every: int = 2000) -> str:
    """Run the arm; commit the volume every ten minutes so a checkpoint outlives the container."""
    run_dir = Path("/data") / out
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["python", "-m", "torch.distributed.run", "--standalone", "--nproc-per-node=1",
           "/root/locallm/train_distributed.py", "--data", f"/data/{data}", *RECIPE,
           "--steps", str(steps), "--save-every", str(save_every), "--out", str(run_dir)]
    if (run_dir / "ckpt.pt").exists():
        cmd.append("--resume")
    log = open(run_dir / "train.log", "a", buffering=1)
    log.write(f"# {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} gpu={GPU} {' '.join(cmd)}\n")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/root/locallm")
    stop = threading.Event()

    def committer():
        while not stop.wait(600):
            volume.commit()
    threading.Thread(target=committer, daemon=True).start()
    for line in proc.stdout:
        log.write(line)
        print(line, end="", flush=True)
    code = proc.wait()
    stop.set()
    log.write(f"# exit {code}\n")
    log.close()
    volume.commit()
    tail = (run_dir / "train.log").read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
    return f"exit {code}\n" + "\n".join(tail)


@app.local_entrypoint()
def main(steps: int = 63111, out: str = "runs/arm-c-matched-code", data: str = "corpus/train.txt",
         save_every: int = 2000):
    print(train.remote(steps, out, data, save_every))
