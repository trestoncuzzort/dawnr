"""Verify a Modal GPU allocation and save its inventory in the existing data volume.

    DAWNR_GPU=A100-80GB modal run --detach t/recipes/modal_gpu_check.py

Uses modal.com/docs/guide/gpu and modal.com/docs/guide/volumes, following
locallm/cloud_train.py. This probe runs no training and times out after two minutes.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import modal

GPU = os.environ.get("DAWNR_GPU", "A100-80GB")
volume = modal.Volume.from_name("dawnr-data")
app = modal.App("dawnr-v6-gpu-check")


@app.function(gpu=GPU, timeout=120, max_containers=1, volumes={"/data": volume})
def check(requested: str) -> dict:
    inventory = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        text=True, timeout=20,
    ).strip().splitlines()
    expected = int(requested.rsplit(":", 1)[1]) if ":" in requested else 1
    if len(inventory) != expected:
        raise RuntimeError(f"nvidia-smi returned {len(inventory)} GPUs, expected {expected}")
    result = {"requested": requested, "inventory": inventory}
    target = Path("/data/v6-20261018/gpu-check.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    volume.commit()
    print(json.dumps(result), flush=True)
    return result


@app.local_entrypoint()
def main():
    call = check.spawn(GPU)
    print(f"Function call: {call.object_id}", flush=True)
    print(json.dumps(call.get()), flush=True)
