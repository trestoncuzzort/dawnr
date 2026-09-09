#!/usr/bin/env python3
"""loop_generate.py -- round N (N > 0) of the t error curve: generate with a
peft LoRA adapter trained by loop_train.py, instead of round 0's ollama path
(spec_experiment.py cmd_generate).

Why this file exists: ollama serves GGUF models and cannot serve a peft
adapter, and there is no GGUF converter on this box (loop_train.py --export
says so itself when it cannot find one). So this generates with transformers
directly: 4-bit bitsandbytes base + PeftModel.from_pretrained(adapter), the
same load path loop_train.py trains with, minus the training-only pieces
(prepare_model_for_kbit_training, gradient checkpointing, the trainer).

It writes raw/<task_id>.json records under spec_experiment.outdir(tag) in
EXACTLY the shape spec_experiment.cmd_generate writes (same keys, same
types), so that `spec_experiment.py extract/tests/table` and `run_par.py`
run unchanged over the output -- only the "how the reply was produced" part
differs; everything downstream reads records, not model servers.

    ~/.venv-train/bin/python loop_generate.py --adapter out/loop/adapter-r1 \\
        --tag qwen2.5-coder-1.5b-r1
    ~/.venv-train/bin/python loop_generate.py --adapter none --tag qwen2.5-coder-1.5b-r0ctl
    ~/.venv-train/bin/python loop_generate.py --adapter out/loop/adapter-r1 \\
        --tag qwen2.5-coder-1.5b-r1 --only-heldout out/loop/heldout.json

GPU selection reads nvidia-smi BEFORE importing torch (loop_train.py's own
pattern, reused verbatim: heavy imports deferred into main() so
CUDA_VISIBLE_DEVICES can be set first). The box is shared, so this always
picks the card with the most free VRAM at launch, unless --gpu pins one. If
every requested id already has a raw/<id>.json on disk, this returns before
touching nvidia-smi or importing torch at all -- a no-op run should not
touch the GPU.

--adapter none loads the bare base through this same code path (4-bit,
same quant config, same generate() call) -- a round-0-equivalent control
that is not ollama, useful for isolating "transformers vs ollama sampling"
from "adapter vs no adapter" if the two ever disagree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import spec_experiment as se   # noqa: E402  (pool, build_prompt, outdir, model_tag)

DEFAULT_BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
MIN_FREE_MIB = 1536   # inference only (no ref model, no optimizer states, no
                       # backward pass); loop_train.py's own 4096 MiB floor is
                       # a training number and does not apply here


# ------------------------------------------------------------- GPU pick --
# Same idea as loop_train.py's free_vram_by_gpu/pick_gpu: read nvidia-smi
# before torch is imported, so CUDA_VISIBLE_DEVICES can still be set.

def free_vram_by_gpu() -> dict[int, int]:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.free",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True)
    d = {}
    for line in out.stdout.strip().splitlines():
        idx, free = line.split(",")
        d[int(idx.strip())] = int(free.strip())
    return d


def pick_gpu(explicit: int | None) -> tuple[int, dict[int, int]]:
    free = free_vram_by_gpu()
    if not free:
        raise SystemExit("nvidia-smi reported no GPUs")
    if explicit is not None:
        return explicit, free
    best = max(free, key=free.get)
    return best, free


# --------------------------------------------------------------- ids --

def select_ids(limit: int, ids_arg: str, only_heldout: str) -> tuple[dict, list]:
    P = se.pool()
    ids = sorted(P)
    if only_heldout:
        held = json.loads(Path(only_heldout).read_text(encoding="utf-8"))
        # out/loop/heldout.json's actual key is "heldout_task_ids"
        # ({"pool_size", "used_task_ids", "heldout_task_ids"} as of 2026-09-09);
        # "heldout" is accepted too in case that shape changes.
        allow = set(held.get("heldout_task_ids") or held.get("heldout") or [])
        ids = [i for i in ids if i in allow]
    if ids_arg:
        want = {int(x) for x in ids_arg.split(",") if x.strip()}
        ids = [i for i in ids if i in want]
    if limit:
        ids = ids[:limit]
    return P, ids


# ------------------------------------------------------------- digest --

def adapter_digest(adapter_dir: Path) -> str:
    """adapter's config hash, or the sha256 of its adapter_model.safetensors
    if present (the actual trained weights, so it changes if a retrain wrote
    a different adapter to the same path)."""
    weights = adapter_dir / "adapter_model.safetensors"
    cfg = adapter_dir / "adapter_config.json"
    if weights.exists():
        h = hashlib.sha256()
        with weights.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return f"weights-sha256:{h.hexdigest()[:16]}"
    if cfg.exists():
        return f"config-sha256:{hashlib.sha256(cfg.read_bytes()).hexdigest()[:16]}"
    return "unknown"


# --------------------------------------------------------------- misc --

def print_followups(tag: str) -> None:
    tag_dir = se.model_tag(tag)
    print()
    print("follow-up commands:")
    print(f"  python3 spec_experiment.py extract --model {tag}")
    print(f"  python3 spec_experiment.py tests    --model {tag}")
    print(f"  python3 run_par.py --tasks out/spec-experiment/{tag_dir}/tasks "
          f"--out out/spec-experiment/{tag_dir}/kernels "
          f"--table out/spec-experiment/{tag_dir}/kernels.md")
    print(f"  python3 spec_experiment.py table    --model {tag} "
          f"--out SPEC-EXPERIMENT-{tag_dir}.md")


# ------------------------------------------------------------------ main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adapter", required=True,
                    help="peft adapter dir (out/loop/adapter-r1), or 'none' for the bare base")
    ap.add_argument("--tag", required=True,
                    help="model tag; records land under out/spec-experiment/<model_tag(tag)>")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="", help="comma-separated task ids, e.g. 100,101")
    ap.add_argument("--gpu", type=int, default=None, help="pin a GPU index; default: most free VRAM")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--only-heldout", default="", help="path to a heldout.json; restricts to its held-out ids")
    ap.add_argument("--seed", type=int, default=1, help="recorded in the digest/options only; generation is greedy")
    ap.add_argument("--min-free-mib", type=int, default=MIN_FREE_MIB)
    args = ap.parse_args()

    d = se.outdir(args.tag)
    P, ids = select_ids(args.limit, args.ids, args.only_heldout)
    todo = [tid for tid in ids if not (d / "raw" / f"{tid}.json").exists()]
    already = len(ids) - len(todo)
    print(f"loop_generate: {len(ids)} problems selected, {already} already on disk, "
          f"{len(todo)} to generate")
    if not todo:
        print("loop_generate: nothing to do (no selected id needs a raw record); "
              "not touching the GPU")
        print_followups(args.tag)
        return 0

    # --------------------------------------------------- GPU, before torch
    gpu, free = pick_gpu(args.gpu)
    print("free VRAM by GPU (MiB): " + ", ".join(f"{i}={m}" for i, m in sorted(free.items())))
    if free.get(gpu, 0) < args.min_free_mib and args.gpu is None:
        print(f"refusing to run: best card is GPU {gpu} with {free[gpu]} MiB free, "
              f"below --min-free-mib={args.min_free_mib}. Not importing torch, not "
              f"touching any GPU.")
        return 3
    print(f"selected GPU {gpu} ({free.get(gpu, '?')} MiB free)")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # ------------------------------------------------------- heavy imports
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    torch.cuda.init()   # lazy CUDA init; without this, reset_peak_memory_stats(dev)
                        # below raises "Invalid device argument" on a torch.device
                        # object (loop_train.py dodges this only because its peft/trl
                        # imports happen to touch CUDA first -- this script does not
                        # import peft until after this point, so it needs the init
                        # explicitly)
    dev = torch.device("cuda:0")   # index 0 WITHIN CUDA_VISIBLE_DEVICES
    torch.cuda.reset_peak_memory_stats(dev)

    print(f"loading tokenizer + base model: {args.base}")
    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16)

    adapter_note = "none"
    adapter_hash = "n/a"
    if args.adapter and args.adapter != "none":
        from peft import PeftModel
        adapter_dir = Path(args.adapter)
        print(f"applying adapter: {adapter_dir}")
        model = PeftModel.from_pretrained(model, str(adapter_dir))
        adapter_note = str(adapter_dir)
        adapter_hash = adapter_digest(adapter_dir)
    model.eval()
    model.config.use_cache = True

    digest = (f"base={args.base} adapter={adapter_note} "
              f"adapter_digest={adapter_hash} torch={torch.__version__} "
              f"transformers={transformers.__version__}")

    options = {"temperature": 0, "seed": args.seed, "max_new_tokens": args.max_new,
               "note": "greedy transformers generate"}

    eos_id = tokenizer.eos_token_id
    if eos_id is None:
        eos_set: set[int] = set()
    elif isinstance(eos_id, int):
        eos_set = {eos_id}
    else:
        eos_set = set(eos_id)

    t_start = time.monotonic()
    asked = 0
    for tid in todo:
        entry = P[tid]
        messages = se.build_prompt(entry)
        t_task0 = time.monotonic()
        # transformers 5.5.0 defaults apply_chat_template(return_tensors="pt") to
        # return_dict=True, i.e. a BatchEncoding, not a bare input_ids tensor --
        # pull input_ids/attention_mask out of it explicitly.
        enc = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
        input_ids = enc["input_ids"].to(dev)
        attention_mask = enc.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(dev)
        prompt_tokens = int(input_ids.shape[-1])

        t_gen0 = time.monotonic()
        with torch.no_grad():
            out = model.generate(
                input_ids, attention_mask=attention_mask, max_new_tokens=args.max_new,
                do_sample=False, pad_token_id=tokenizer.pad_token_id, eos_token_id=eos_id)
        eval_s = time.monotonic() - t_gen0

        new_tokens = out[0][input_ids.shape[-1]:]
        reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
        reply_tokens = int(new_tokens.shape[-1])
        hit_eos = reply_tokens > 0 and int(new_tokens[-1].item()) in eos_set
        done_reason = "stop" if hit_eos else "length"

        wall = time.monotonic() - t_task0

        record = {"task_id": tid, "fn": entry["fn"], "model": args.tag, "digest": digest,
                  "options": options, "messages": messages, "reply": reply,
                  "prompt_tokens": prompt_tokens, "reply_tokens": reply_tokens,
                  "eval_s": round(eval_s, 3), "wall_s": round(wall, 3),
                  "done_reason": done_reason}
        (d / "raw" / f"{tid}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        asked += 1
        if asked % 10 == 0 or asked == 1:
            el = time.monotonic() - t_start
            print(f"generate: {already + asked}/{len(ids)} ({asked} asked this run, "
                  f"{el:.0f} s, {el / asked:.1f} s each)", flush=True)

    wall_total = time.monotonic() - t_start
    peak = torch.cuda.max_memory_allocated(dev) / 1e9
    print(f"generate: {already + asked} of {len(ids)} problems have a reply on disk")
    print(f"peak VRAM: {peak:.2f} GB")
    print(f"wall time: {wall_total:.1f} s ({wall_total / max(asked, 1):.1f} s/problem)")
    print(f"GPU used: {gpu}")
    print_followups(args.tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
