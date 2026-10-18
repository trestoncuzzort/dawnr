"""Export a v6 adapter against its explicit pinned base, preserving input identities.

Follows student_sft.merge and gcp-student-2026-10-11-export.sh.
Sources: https://huggingface.co/docs/peft/package_reference/lora
https://github.com/ggml-org/llama.cpp/tree/f1cee9941b0e843ea260bf8dd9a090fbd9711b6a
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
CONVERTER = "f1cee9941b0e843ea260bf8dd9a090fbd9711b6a"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_adapter(adapter, manifest):
    record = json.loads(Path(manifest).read_text())
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        if name not in record["files"] or digest(Path(adapter) / name) != record["files"][name]:
            raise ValueError(f"adapter identity mismatch: {name}")
    return record


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adapter", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--llama-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    p.add_argument("--name", required=True)
    a = p.parse_args(argv)
    source = verify_adapter(a.adapter, a.manifest)
    actual = subprocess.check_output(["git", "-C", str(a.llama_dir), "rev-parse", "HEAD"], text=True).strip()
    if actual != CONVERTER:
        p.error("converter checkout differs from the registered revision")
    if subprocess.check_output(["git", "-C", str(a.llama_dir), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        p.error("converter tracked files are modified")
    if a.out.exists():
        p.error("use a fresh export directory; never overwrite a model or partial export")
    a.out.mkdir(parents=True)
    import torch
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    snapshot = Path(snapshot_download(
        MODEL, revision=REVISION, local_files_only=True,
        allow_patterns=["config.json", "model*.safetensors", "model.safetensors.index.json",
                        "tokenizer.json", "tokenizer_config.json", "chat_template.jinja"]))
    if snapshot.name != REVISION:
        raise RuntimeError("base snapshot does not match the registered revision")
    inputs = {path.name: digest(path) for path in sorted(snapshot.iterdir()) if path.is_file()}
    receipt = {"base": MODEL, "revision": REVISION, "base_files": inputs, "adapter": source,
               "converter_commit": CONVERTER, "merge_dtype": "bfloat16", "quantization": "Q8_0",
               "name": a.name, "versions": {n: __import__(n).__version__ for n in ("torch", "transformers", "peft")}}
    (a.out / "inputs.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base = AutoModelForCausalLM.from_pretrained(str(snapshot), dtype=torch.bfloat16,
                                              device_map={"": "cpu" if a.device == "cpu" else 0})
    model = PeftModel.from_pretrained(base, str(a.adapter)).merge_and_unload(safe_merge=True)
    model.config._name_or_path = MODEL
    merged = a.out / "merged"
    model.save_pretrained(merged)
    AutoTokenizer.from_pretrained(str(snapshot)).save_pretrained(merged)
    del model, base
    import gc
    gc.collect()
    if a.device == "cuda":
        torch.cuda.empty_cache()
    gguf = a.out / "model-Q8_0.gguf"
    subprocess.run([sys.executable, str(a.llama_dir / "convert_hf_to_gguf.py"), str(merged),
                    "--outfile", str(gguf), "--outtype", "q8_0", "--no-mtp", "--model-name", a.name], check=True)
    with gguf.open("rb") as stream:
        magic = stream.read(4)
    if gguf.stat().st_size < 1024 or magic != b"GGUF":
        raise RuntimeError("converter did not write a GGUF model")
    receipt["output"] = {"filename": gguf.name, "bytes": gguf.stat().st_size, "sha256": digest(gguf)}
    (a.out / "export.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (a.out / "SHA256SUMS").write_text(f"{receipt['output']['sha256']}  {gguf.name}\n")
    print(json.dumps(receipt["output"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
