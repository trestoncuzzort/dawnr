"""The teacher served on a rented GPU (Modal): vLLM's OpenAI-compatible server behind the
pipeline's own client.

t/EXPERT-ITERATION-2026-09-26.md staged 442 specification prompts and 368 training-problem
prompts for the prompted 27B teacher and generated nothing, because the shared cards never had the
30 GB the teacher needs. This serves the same teacher on one rented H100 so the two generation
commands the design names run unchanged against it:

    modal deploy locallm/cloud_serve.py                 # prints the server's URL once the app is deployed
    export T_API_KEY=<the key given as DAWNR_TEACHER_KEY at deploy time>
    python3 t/rl_teacher_expert_iter.py sample-spec --host https://<url>/v1 --model Qwen/Qwen3.8-27B-FP8 ...
    python3 t/spec_experiment.py generate --api openai --host https://<url>/v1 --model Qwen/Qwen3.8-27B-FP8 ...

The client (t/spec_experiment.py chat, api "openai") posts to <host>/chat/completions with
`Authorization: Bearer $T_API_KEY`; vLLM's `--api-key` checks that bearer, which is what keeps a
public URL private. The pattern (image, cached weights on a Volume, `app.server` with a port,
`vllm serve` in a subprocess) is Modal's own vLLM example (modal.com/docs/examples/vllm_inference,
fetched 2026-09-30); vLLM is pinned to the version the lab serves with. A container that has been
idle for `scaledown_window` stops, so the spend ends with the last request.

Research only (release.py names it so). Nothing here names a person, a machine or an account.
"""
from __future__ import annotations

import os
import subprocess

import modal

MODEL = os.environ.get("DAWNR_TEACHER", "Qwen/Qwen3.8-27B-FP8")
GPU = os.environ.get("DAWNR_GPU", "H100")
API_KEY = os.environ.get("DAWNR_TEACHER_KEY", "dawnr-teacher")   # the client's T_API_KEY
MAX_LEN = int(os.environ.get("DAWNR_MAX_LEN", "8192"))            # the v5 prompt is 3,073 tokens
SCALEDOWN_S = int(os.environ.get("DAWNR_SCALEDOWN_S", str(10 * 60)))
VLLM = os.environ.get("DAWNR_VLLM", "vllm==0.29.0")               # the lab's version, 2026-09-30
GPU_UTIL = os.environ.get("DAWNR_GPU_UTIL", "0.85")               # a 0.5B smoke at 0.90 ran a 22 GB card out at init
MAX_SEQS = os.environ.get("DAWNR_MAX_SEQS", "32")                 # the client sends at most --jobs requests at once

# The module runs twice: on the deploying machine (where DAWNR_* are set) and inside the container
# (where they are not), so every setting is baked into the image's environment at deploy time.
image = (modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
         .entrypoint([])
         .uv_pip_install(VLLM)
         .env({"HF_XET_HIGH_PERFORMANCE": "1", "DAWNR_TEACHER": MODEL, "DAWNR_TEACHER_KEY": API_KEY,
               "DAWNR_MAX_LEN": str(MAX_LEN), "DAWNR_GPU_UTIL": GPU_UTIL, "DAWNR_MAX_SEQS": MAX_SEQS}))
hf_cache = modal.Volume.from_name("dawnr-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("dawnr-vllm-cache", create_if_missing=True)
app = modal.App("dawnr-teacher", image=image)


@app.server(gpu=GPU, port=8000, scaledown_window=SCALEDOWN_S, startup_timeout=20 * 60,
            volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
            unauthenticated=True, target_concurrency=16, max_containers=1)
class Server:
    """vLLM's server on port 8000; the first start downloads the weights into the Volume. The
    vision side of the checkpoint is switched off (--limit-mm-per-prompt), as Modal's example does
    for a multimodal model served for text."""

    @modal.enter()
    def start(self):
        import json
        cmd = ["vllm", "serve", MODEL, "--served-model-name", MODEL, "--host", "0.0.0.0", "--port", "8000",
               "--api-key", API_KEY, "--max-model-len", str(MAX_LEN), "--gpu-memory-utilization", GPU_UTIL,
               "--max-num-seqs", MAX_SEQS, "--limit-mm-per-prompt", json.dumps({"image": 0, "video": 0, "audio": 0})]
        print("starting:", " ".join(cmd), flush=True)
        self.process = subprocess.Popen(cmd)

    @modal.exit()
    def stop(self):
        self.process.terminate()
