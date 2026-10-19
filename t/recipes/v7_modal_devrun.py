"""Export and generation for the v7 development run on Modal, so nothing runs on the laptop.

Two images, both the pinned toolchain moved to the cloud:
  - export: v6_modal's training image (torch/transformers/peft) plus the pinned llama.cpp source
    (commit f1cee994), running the frozen t/recipes/v6_export.py (merge adapter -> Q8_0 GGUF).
  - serve: an NVIDIA CUDA image with that same llama.cpp built (the exact flags of
    t/recipes/v6-gcp-inference-setup.sh), bubblewrap for the Python test sandbox, and dawnr's t/
    plus nl/data mounted, running t/recipes/v6_server_route.py against a local llama-server.

    modal run --detach t/recipes/v7_modal_devrun.py --mode build_smoke   # build serve image, check it
    modal run --detach t/recipes/v7_modal_devrun.py --mode export
    modal run --detach t/recipes/v7_modal_devrun.py --mode generate

Grading is t/recipes/v7_modal_grade.py (already proven). Sources: t/recipes/v6-gcp-inference-setup.sh;
t/recipes/v6_export.py; t/recipes/v6_server_route.py; modal.com/docs/guide/existing-images
(receipt v7modalgrade).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from v6_modal import data, models, CACHE, MODEL, REVISION  # noqa: E402 (constants + volumes only)

LLAMA_COMMIT = "f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"
STAGED_SERVE = Path(os.environ.get("V7_STAGED_SERVE", "/home/t/.claude/jobs/d76813cf/tmp/dawnr-serve"))
RUN = "/data/v7-20261019"

# Export: v6_modal's pinned training deps (replicated here rather than extending its image, which
# already ends with an add_local_file and so cannot take further build steps) plus the pinned
# llama.cpp source, so the frozen t/recipes/v6_export.py (merge adapter -> Q8_0) runs unchanged.
export_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install("torch==2.9.1", index_url="https://download.pytorch.org/whl/cu129")
    .pip_install("transformers==5.20.1", "peft==0.21.2", "bitsandbytes==0.50.2",
                 "accelerate==1.15.0", "jinja2==3.1.6", "numpy==2.2.6",
                 "safetensors==0.8.0", "huggingface-hub==2.2.0", "sentencepiece==0.2.0")
    .apt_install("git", "cmake", "build-essential", "curl")
    .run_commands(
        "git init /opt/llama && cd /opt/llama && git remote add origin https://github.com/ggml-org/llama.cpp.git"
        f" && git fetch --depth 1 origin {LLAMA_COMMIT} && git checkout --detach FETCH_HEAD",
        "cd /opt/llama && pip install -e gguf-py",
    )
    .env({"HF_HUB_CACHE": CACHE, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"})
    .add_local_dir(str(STAGED_SERVE / "t"), "/opt/dawnr/t", copy=True)
)

# Serve: CUDA devel (nvcc to build, libs to run), the pinned llama.cpp compiled, bubblewrap for the
# generation sandbox, add_python for Modal's wrapper, dawnr t/ + nl/data mounted.
serve_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu24.04", add_python="3.12")
    .apt_install("git", "cmake", "build-essential", "curl", "libgomp1", "bubblewrap", "libcurl4-openssl-dev")
    .run_commands(
        "git init /opt/llama && cd /opt/llama && git remote add origin https://github.com/ggml-org/llama.cpp.git"
        f" && git fetch --depth 1 origin {LLAMA_COMMIT} && git checkout --detach FETCH_HEAD",
        "cd /opt/llama && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON"
        " -DCMAKE_CUDA_ARCHITECTURES='80;86;89;90' -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF"
        " && cmake --build build --target llama-server llama-quantize llama-gguf-split -j 8",
    )
    .env({"PYTHONUNBUFFERED": "1"})
    .add_local_dir(str(STAGED_SERVE / "t"), "/opt/dawnr/t", copy=True)
    .add_local_dir(str(STAGED_SERVE / "nl"), "/opt/dawnr/nl", copy=True)
)

app = modal.App("dawnr-v7-devrun")
SERVER = "/opt/llama/build/bin/llama-server"


@app.function(image=serve_image, cpu=4, memory=8192, timeout=900)
def build_smoke() -> dict:
    """No GPU: prove the pinned llama-server built and the bubblewrap sandbox runs in this container."""
    import subprocess

    ver = subprocess.run([SERVER, "--version"], capture_output=True, text=True)
    sys.path.insert(0, "/opt/dawnr/t")
    import py_sandbox

    ok = py_sandbox.available()
    why = "" if ok else py_sandbox.why_unavailable()
    probe = py_sandbox.run_tests("def f(x):\n    return x+1\n", ["assert f(1)==2"]) if ok else {}
    return {"llama_version": (ver.stdout + ver.stderr).strip()[-200:], "returncode": ver.returncode,
            "sandbox_available": ok, "sandbox_why": why, "sandbox_probe": probe}


@app.function(image=export_image, gpu="L4", cpu=8, memory=32768, timeout=2400,
              volumes={"/data": data, "/models": models})
def export() -> dict:
    """Merge the finalized v7 adapter and convert to Q8_0 with the pinned converter (v6_export.py)."""
    import subprocess

    os.environ["HF_HUB_CACHE"] = CACHE
    adapter = Path(RUN) / "adapter"
    manifest = Path(RUN) / "manifest.json"
    out = Path(RUN) / "export"
    if (out / "export.json").exists():
        return json.loads((out / "export.json").read_text())["output"]
    cmd = ["python", "/opt/dawnr/t/recipes/v6_export.py", "--adapter", str(adapter),
           "--manifest", str(manifest), "--llama-dir", "/opt/llama", "--out", str(out),
           "--device", "cuda", "--name", "dawnr-v7-20261019"]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=2200,
                          env={**os.environ, "HF_HUB_OFFLINE": "1"})
    (Path(RUN) / "export-v7.log").write_text(proc.stdout + "\n--STDERR--\n" + proc.stderr)
    data.commit()
    if proc.returncode:
        raise RuntimeError("export failed; see export-v7.log:\n" + proc.stderr[-1500:])
    return json.loads((out / "export.json").read_text())["output"]


@app.function(image=serve_image, gpu="L4", cpu=8, memory=32768, timeout=3 * 3600,
              volumes={"/data": data})
def generate() -> dict:
    """Serve the v7 Q8 and run the frozen Python-first route on the 95-problem development panel."""
    import shutil
    import subprocess
    import time
    import urllib.request

    export_rec = json.loads((Path(RUN) / "export/export.json").read_text())
    gguf = Path(RUN) / "export" / export_rec["output"]["filename"]
    sha = export_rec["output"]["sha256"]
    identity = f"student-v7:{sha}:llama-{LLAMA_COMMIT}"
    panel = Path(RUN) / "dev-95.txt"
    tag = "v7-20261019-dev"

    server = subprocess.Popen(
        [SERVER, "--model", str(gguf), "--alias", "dawnr-v7", "--host", "127.0.0.1", "--port", "8847",
         "--n-gpu-layers", "99", "--threads", "8", "--threads-batch", "8", "--parallel", "4",
         "--ctx-size", "16384", "--chat-template-kwargs", '{"enable_thinking":false}'],
        stdout=open(Path(RUN) / "server-v7.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(240):
            try:
                if urllib.request.urlopen("http://127.0.0.1:8847/health", timeout=2).status == 200:
                    break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("llama-server did not become healthy")
        route = ["python", "/opt/dawnr/t/recipes/v6_server_route.py",
                 "--endpoint", "http://127.0.0.1:8847/v1/chat/completions", "--model", "dawnr-v7",
                 "--identity", identity, "--cache", f"{RUN}/requests", "--concurrency", "4",
                 "--", "--tag", tag, "--ids-file", str(panel), "--pool", "v5", "--python", "3",
                 "--spec-samples", "4", "--per-problem", "3", "--samples", "2", "--max-new", "1024", "--batch", "16"]
        proc = subprocess.run(route, text=True, capture_output=True, timeout=3 * 3600 - 600,
                              cwd="/opt/dawnr", env={**os.environ, "PYTHONPATH": "/opt/dawnr/t"})
        (Path(RUN) / "route-v7.log").write_text(proc.stdout + "\n--STDERR--\n" + proc.stderr)
        src = Path(f"/opt/dawnr/t/out/spec-experiment/{tag}")
        dst = Path(RUN) / "spec-experiment" / tag
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        data.commit()
        if proc.returncode:
            raise RuntimeError("route failed; see route-v7.log:\n" + proc.stderr[-1500:])
        summary = json.loads((src / "spec_first.json").read_text())
        return {"answered": summary.get("answered"),
                "python_test_passing": summary.get("with a tested Python solution"),
                "tag": tag, "identity": identity}
    finally:
        server.terminate()


@app.local_entrypoint()
def main(mode: str = "build_smoke"):
    fns = {"build_smoke": build_smoke, "export": export, "generate": generate}
    if mode not in fns:
        raise ValueError("mode must be build_smoke, export or generate")
    print(json.dumps(fns[mode].remote(), indent=2), flush=True)
