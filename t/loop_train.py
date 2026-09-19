#!/usr/bin/env python3
"""loop_train.py -- QLoRA SFT and DPO on the base named by --model, over
the examples and bugs loop_dataset.py built (default: Qwen2.5-Coder-1.5B).

House pattern is forge/train_dpo.py (this repo's earlier DPO pipeline, for a
different task): 4-bit base + a LoRA adapter over the attention and MLP
projections, trained with trl's DPOTrainer. Two things differ on purpose:

  - no unsloth. Nothing here imports unsloth or drives Ollama; the base
    loads through plain transformers + bitsandbytes + peft, and the model
    itself (not a GGUF) is what trains.
  - no merge-free adapter-at-inference path. --export here MERGES the
    trained LoRA into the base in bf16 (peft's merge_and_unload) and saves
    that model, then hands it to llama.cpp's convert script if one is on
    this box; forge/export_adapter.py's own comment explains why a 4-bit
    base cannot be converted directly (bitsandbytes configs are not a
    convert_hf_to_gguf.py quant method), which is exactly why the merge
    happens in bf16 against the full-precision base, never the 4-bit one.

The prompt is the model's OWN chat template applied to the recorded
system+user messages (out/loop/pairs.jsonl's "prompt" list), rendered once
at dataset-build time with add_generation_prompt=True; "chosen" and
"rejected" stay the plain assistant text loop_dataset.py already printed
with surface.print_task. This is loop_dataset.py's contract, read literally:
"the prompt is the recorded system+user messages, the completion is the
assistant answer".

GPU selection reads nvidia-smi BEFORE importing torch (heavy imports are
deferred into main() for exactly this reason) so CUDA_VISIBLE_DEVICES can be
set first; the box is shared, so this always picks the card with the most
free VRAM at launch, unless --gpu pins one.

    python3 loop_train.py --smoke
    python3 loop_train.py --sft-first --steps 200 --out out/loop/adapter
    python3 loop_train.py --out out/loop/adapter --export
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from importlib import metadata

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_PAIRS = HERE / "out" / "loop" / "pairs.jsonl"
DEFAULT_SFT = HERE / "out" / "loop" / "sft.jsonl"
DEFAULT_OUT = HERE / "out" / "loop" / "adapter"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]
MIN_FREE_MIB = 4096      # historical 1.5B admission floor, not a training-memory guarantee
TOKENIZER_PROBES = (
    "t 1 task f(x: int) returns (r: int)",
    "t 1\ntask f(x: int) returns (r: int) {\n  r = x / 2\n}\n",
    "if x <= 0 then [1, 2] else [x % 3]",
)


# ------------------------------------------------------------- GPU pick --

def free_vram_by_gpu() -> dict[int, int]:
    """{gpu index: free MiB}, from nvidia-smi. Never touches torch/CUDA."""
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,memory.free",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True, timeout=10)
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
        if explicit not in free:
            raise ValueError(f"GPU {explicit} is not present in nvidia-smi's report")
        return explicit, free
    best = max(free, key=free.get)
    return best, free


def require_gpu_space(gpu: int, free: dict[int, int], minimum: int) -> None:
    """A pin chooses a card; it does not waive the same admission check."""
    if minimum <= 0:
        raise ValueError("--min-free-mib must be positive")
    if gpu not in free or free[gpu] < minimum:
        raise ValueError(f"GPU {gpu} has {free.get(gpu, 0)} MiB free, below --min-free-mib={minimum}")


# ------------------------------------------------------------- tokenizer --

def tokenizer_is_faithful(tokenizer) -> bool:
    return all(tokenizer.decode(tokenizer(probe, add_special_tokens=False)["input_ids"],
                                skip_special_tokens=True, clean_up_tokenization_spaces=False) == probe
               for probe in TOKENIZER_PROBES)


def repair_tokenizer(tokenizer, fallback):
    """Use the model's actual tokenization graph when class detection destroys spaces."""
    if not tokenizer_is_faithful(tokenizer):
        print(f"{type(tokenizer).__name__} does not round-trip t; loading tokenizer.json directly", flush=True)
        alternative = fallback()
        for attr in ("eos_token", "pad_token", "bos_token", "unk_token", "additional_special_tokens"):
            value = getattr(tokenizer, attr, None)
            if value is not None and not getattr(alternative, attr, None):
                setattr(alternative, attr, value)
        alternative.chat_template = alternative.chat_template or tokenizer.chat_template
        tokenizer = alternative
    if not tokenizer_is_faithful(tokenizer):
        raise ValueError("Tokenizer does not preserve t text; refusing to train")
    if not tokenizer.chat_template:
        raise ValueError("Tokenizer has no chat template; refusing to invent the training prompt")
    if tokenizer.eos_token is None:
        raise ValueError("Tokenizer has no EOS token")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def load_tokenizer(model_name: str):
    from transformers import AutoTokenizer, PreTrainedTokenizerFast
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def fallback():
        local = Path(model_name) / "tokenizer.json"
        if local.is_file():
            path = str(local)
        else:
            from huggingface_hub import hf_hub_download
            path = hf_hub_download(model_name, "tokenizer.json",
                                   revision=tokenizer.init_kwargs.get("_commit_hash"))
        return PreTrainedTokenizerFast(tokenizer_file=path)

    return repair_tokenizer(tokenizer, fallback)


# -------------------------------------------------------------- records --

def file_record(path: Path) -> dict:
    return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_run_record(out_dir: Path, record: dict, stage: str, **updates) -> None:
    record.update(updates, stage=stage, updated=time.time())
    temporary = out_dir / "run.json.tmp"
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(out_dir / "run.json")


def persist_stage(trainer, tokenizer, destination: Path, stage: str, metrics: dict) -> None:
    """Save the warm-up before DPO can fail, and record completed trainer steps/metrics."""
    trainer.save_model(str(destination))
    tokenizer.save_pretrained(str(destination))
    trainer.save_state()
    trainer.save_metrics(stage, metrics)


def sft_length_kwargs(config_class, max_len: int) -> dict:
    params = inspect.signature(config_class.__init__).parameters
    for name in ("max_length", "max_seq_length"):
        if name in params:
            return {name: max_len}
    raise ValueError("SFTConfig exposes no supported sequence-length setting")


# --------------------------------------------------------------- dataset --

def _kwargs_for(cls, wanted: dict) -> dict:
    """Filter `wanted` down to the constructor's actual parameters, so this
    file does not hardcode one trl version's kwarg names.

    It says what it dropped. The original note here said silent dropping was fine because every dropped key
    matched a default anyway; that stopped being true when trl reached 1.13 and removed `use_logits_to_keep`,
    which was not a default but this file's whole memory strategy -- logits for the completion tokens only.
    It vanished without a word and DPO went back to full-window, full-vocabulary logits, which is what put the
    round 5 student out of memory on a 16 GB card (2026-09-18). A dropped key is now printed, so the next
    version that removes a guarantee says so."""
    try:
        params = inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):
        return dict(wanted)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(wanted)
    kept = {k: v for k, v in wanted.items() if k in params}
    dropped = [k for k in wanted if k not in kept]
    if dropped:
        print(f"note: {cls.__name__} in this version takes none of {', '.join(sorted(dropped))}; "
              f"whatever those asked for is not in force")
    return kept


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def render_prompt(tokenizer, messages: list[dict]) -> str:
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)


def build_pair_dataset(tokenizer, path: Path, max_len: int, counts: dict | None = None):
    from datasets import Dataset
    rows = load_jsonl(path)
    prompts, chosen, rejected = [], [], []
    truncated = 0
    for r in rows:
        if not all(isinstance(r.get(k), str) and r[k].strip() for k in ("chosen", "rejected")):
            raise ValueError("A DPO pair has an empty chosen or rejected answer")
        p = render_prompt(tokenizer, r["prompt"])
        if len(tokenizer(p, add_special_tokens=False)["input_ids"]) >= max_len:
            continue  # TRL keep_start would remove every answer token.
        truncated += any(len(tokenizer(p + r[k], add_special_tokens=False)["input_ids"]) > max_len
                         for k in ("chosen", "rejected"))
        prompts.append(p)
        chosen.append(r["chosen"])
        rejected.append(r["rejected"])
    ds = Dataset.from_dict({"prompt": prompts, "chosen": chosen, "rejected": rejected})
    if counts is not None:
        counts.update(input=len(rows), kept=len(ds), no_answer_tokens=len(rows) - len(ds), partial_answers=truncated)
    if not len(ds):
        raise ValueError("No DPO pairs retain answer tokens at --max-len; increase the window")
    return ds


def build_sft_dataset(tokenizer, path: Path, max_len: int | None = None, counts: dict | None = None):
    from datasets import Dataset
    rows = load_jsonl(path)
    texts = []
    eos = tokenizer.eos_token or ""
    truncated = 0
    for r in rows:
        if not isinstance(r.get("chosen"), str) or not r["chosen"].strip():
            raise ValueError("An SFT row has no assistant answer")
        p = render_prompt(tokenizer, r["prompt"])
        if max_len and len(tokenizer(p, add_special_tokens=False)["input_ids"]) >= max_len:
            continue
        text = p + r["chosen"] + ("" if r["chosen"].endswith(eos) else eos)
        truncated += bool(max_len and len(tokenizer(text, add_special_tokens=False)["input_ids"]) > max_len)
        texts.append(text)
    if counts is not None:
        counts.update(input=len(rows), kept=len(texts), no_answer_tokens=len(rows) - len(texts), partial_answers=truncated)
    if not texts:
        raise ValueError("No SFT examples retain answer tokens at --max-len; increase the window")
    return Dataset.from_dict({"text": texts})


# ------------------------------------------------------------------ main --

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--pairs", default=str(DEFAULT_PAIRS))
    ap.add_argument("--sft", default=str(DEFAULT_SFT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--sft-first", action="store_true",
                    help="one warm-up epoch on --sft before DPO")
    ap.add_argument("--steps", type=int, default=None, help="max DPO steps")
    ap.add_argument("--epochs", type=float, default=1.0, help="DPO epochs (ignored if --steps set)")
    ap.add_argument("--lr", type=float, default=5e-6)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=1, help="adapter initialization and trainer/data RNG seed")
    ap.add_argument("--save-steps", type=int, default=25, help="save a resumable checkpoint every N optimizer steps")
    ap.add_argument("--gpu", type=int, default=None, help="pin a GPU index; default: most free VRAM")
    ap.add_argument("--min-free-mib", type=int, default=None,
                    help="admission floor on the chosen GPU; required for a nondefault base model")
    ap.add_argument("--smoke", action="store_true", help="5 steps, batch 1, no --steps/--batch needed")
    ap.add_argument("--export", action="store_true",
                    help="after training: merge adapter into base (bf16), save, try GGUF")
    args = ap.parse_args()
    if args.min_free_mib is None:
        if args.model != DEFAULT_MODEL:
            ap.error("set --min-free-mib for this base; the historical 1.5B floor is not a 7B memory estimate")
        args.min_free_mib = MIN_FREE_MIB
    if min(args.batch, args.grad_accum, args.max_len, args.save_steps, args.min_free_mib) <= 0:
        ap.error("batch, grad-accum, max-len, save-steps and min-free-mib must be positive")
    if args.steps is not None and args.steps <= 0:
        ap.error("--steps must be positive")

    if args.smoke:
        args.steps = 5
        args.batch = 1
        args.grad_accum = 1
        args.max_len = min(args.max_len, 256)   # box is shared; keep the smoke footprint small

    # --------------------------------------------------- GPU, before torch
    try:
        gpu, free = pick_gpu(args.gpu)
        require_gpu_space(gpu, free, args.min_free_mib)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"refusing to run: {exc}. Not importing torch or allocating GPU memory.")
        return 3
    print("free VRAM by GPU (MiB): " + ", ".join(f"{i}={m}" for i, m in sorted(free.items())))
    print(f"selected GPU {gpu} ({free.get(gpu, '?')} MiB free)")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    # this box's other GPU users make free memory a moving target; reduce
    # fragmentation rather than assume the nvidia-smi snapshot above still
    # holds by the time the first backward pass runs.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # ------------------------------------------------------- heavy imports
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, set_seed
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import DPOConfig, DPOTrainer

    set_seed(args.seed)  # before model loading and LoRA initialization, not just Trainer construction
    torch.cuda.init()
    dev = torch.device("cuda:0")   # index 0 WITHIN CUDA_VISIBLE_DEVICES
    if not torch.cuda.is_bf16_supported():
        raise ValueError("The selected GPU does not support this BF16 training recipe")
    torch.cuda.reset_peak_memory_stats(dev)
    t_start = time.monotonic()

    print(f"loading tokenizer + base model: {args.model}")
    tokenizer = load_tokenizer(args.model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    dpo_counts, sft_counts = {}, {}
    dpo_ds = build_pair_dataset(tokenizer, Path(args.pairs), args.max_len, dpo_counts)
    sft_ds = build_sft_dataset(tokenizer, Path(args.sft), args.max_len, sft_counts) if args.sft_first else None
    run_record = {
        "schema": 1, "started": time.time(), "model": args.model, "seed": args.seed,
        "source": file_record(Path(__file__)), "pairs": file_record(Path(args.pairs)),
        "sft": file_record(Path(args.sft)) if args.sft_first else None,
        "tokenizer": {"class": type(tokenizer).__name__, "roundtrip": True,
                      "chat_template_sha256": hashlib.sha256(
                          json.dumps(tokenizer.chat_template, sort_keys=True).encode()).hexdigest()},
        "versions": {p: metadata.version(p) for p in
                     ("torch", "transformers", "trl", "peft", "datasets", "bitsandbytes", "accelerate")},
        "config": {k: getattr(args, k) for k in
                   ("steps", "epochs", "lr", "batch", "grad_accum", "max_len", "save_steps", "sft_first")},
        "lora": {"r": 16, "alpha": 16, "dropout": 0.0, "target_modules": TARGET_MODULES},
        "gpu": {"index": gpu, "free_mib_at_admission": free[gpu], "minimum_free_mib": args.min_free_mib},
        "dataset": {"sft": sft_counts, "dpo": dpo_counts},
    }
    write_run_record(out_dir, run_record, "loading")
    print("training rows: " + json.dumps(run_record["dataset"], sort_keys=True))

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(r=16, lora_alpha=16, lora_dropout=0.0, bias="none",
                      target_modules=TARGET_MODULES, task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()   # QLoRA + grad checkpointing: the frozen
                                          # 4-bit base needs this or no grad flows
                                          # into the LoRA adapters at all.
    if not hasattr(model, "warnings_issued"):
        # trl's *Trainer classes still poke model.warnings_issued["estimate_tokens"]
        # (an old transformers.Trainer suppression flag); transformers 5.5.0 no
        # longer sets it on PreTrainedModel, so trl's own AttributeError needs
        # heading off here rather than by downgrading either package.
        model.warnings_issued = {}

    # ---------------------------------------------------- optional SFT warm-up
    if args.sft_first:
        from trl import SFTConfig, SFTTrainer
        sft_path = Path(args.sft)
        print(f"SFT warm-up on {sft_path}")
        sft_wanted = dict(
            output_dir=str(out_dir / "sft-warmup"),
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=1, learning_rate=args.lr, bf16=True,
            logging_steps=1, max_steps=(5 if args.smoke else -1),
            dataset_text_field="text", **sft_length_kwargs(SFTConfig, args.max_len),
            seed=args.seed, data_seed=args.seed,
            save_strategy="steps", save_steps=args.save_steps, save_total_limit=2,
            optim="paged_adamw_8bit", gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
            report_to=[])
        sft_cfg = SFTConfig(**_kwargs_for(SFTConfig, sft_wanted))
        sft_trainer_kwargs = dict(model=model, args=sft_cfg, train_dataset=sft_ds,
                                  tokenizer=tokenizer, processing_class=tokenizer)
        sft_trainer = SFTTrainer(**_kwargs_for(SFTTrainer, sft_trainer_kwargs))
        if not len(sft_trainer.train_dataset):
            raise ValueError("SFT preprocessing retained no training examples")
        sft_counts["trainer_rows"] = len(sft_trainer.train_dataset)
        write_run_record(out_dir, run_record, "sft_running")
        sft_result = sft_trainer.train()
        persist_stage(sft_trainer, tokenizer, out_dir / "sft-warmup", "sft", sft_result.metrics)
        write_run_record(out_dir, run_record, "sft_complete", sft_metrics=sft_result.metrics)
        print("SFT warm-up done")
        # The warm-up's trainer holds its optimiser state, its gradient buffers and its accelerator on the same
        # card DPO is about to use. Left alive they cost about as much as the DPO step itself, and on 2026-09-18
        # that was the difference between a step and CUDA out of memory at a 76 MB allocation with 88 MB free
        # (measured: the failure did not move when the window went from 4,608 tokens to 3,584, so the window was
        # never what filled the card).
        import gc
        sft_trainer.model = None
        del sft_trainer, sft_ds
        gc.collect()
        torch.cuda.empty_cache()
        if torch.cuda.is_available():
            print(f"after the warm-up: {torch.cuda.memory_allocated()/2**30:.1f} GiB still held, "
                  f"{torch.cuda.memory_reserved()/2**30:.1f} GiB reserved")

    # --------------------------------------------------------------- DPO
    print(f"DPO pairs: {len(dpo_ds)}")

    dpo_wanted = dict(
        output_dir=str(out_dir), per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum, warmup_ratio=0.1,
        num_train_epochs=args.epochs, max_steps=(args.steps or -1),
        learning_rate=args.lr, beta=0.1, bf16=True, optim="paged_adamw_8bit",
        # The same prompt occupies different numbers of tokens in each base. Dataset counts above expose
        # the answers a window loses; a Qwen-sized window cannot be assumed to fit the prover tokenizer.
        logging_steps=1, max_length=args.max_len,
        seed=args.seed, data_seed=args.seed,
        save_strategy="steps", save_steps=args.save_steps, save_total_limit=2,
        # TRL 1.13 computes full-window logits. Cache the frozen post-SFT adapter's reference pass once,
        # before the policy's training graph exists, in batches of one pair.
        precompute_ref_log_probs=True,
        precompute_ref_batch_size=1,
        # the activations of a 3,300-token pair, recomputed rather than kept: the card is 200 MB short of the
        # 1.84 GiB logits tensor without this, measured 2026-09-18
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        # SDPA must see separate sequences. TRL's collator already pads only to the batch's longest pair;
        # flattening with padding_free would need a FlashAttention implementation that respects boundaries.
        padding_free=False,
        report_to=[])
    dpo_cfg = DPOConfig(**_kwargs_for(DPOConfig, dpo_wanted))

    dpo_trainer_kwargs = dict(model=model, args=dpo_cfg, train_dataset=dpo_ds,
                              tokenizer=tokenizer, processing_class=tokenizer)
    trainer = DPOTrainer(**_kwargs_for(DPOTrainer, dpo_trainer_kwargs))
    if not len(trainer.train_dataset):
        raise ValueError("DPO preprocessing retained no training pairs")
    dpo_counts["trainer_rows"] = len(trainer.train_dataset)
    write_run_record(out_dir, run_record, "dpo_running")

    print(f"training: steps={args.steps} epochs={args.epochs} lr={args.lr} "
          f"batch={args.batch} grad_accum={args.grad_accum} max_len={args.max_len} seed={args.seed}")
    result = trainer.train()

    wall = time.monotonic() - t_start
    peak = torch.cuda.max_memory_allocated(dev) / 1e9
    print(f"trained: {result}")
    print(f"peak VRAM: {peak:.2f} GB")
    print(f"wall time: {wall:.1f} s")
    print(f"GPU used: {gpu}")

    persist_stage(trainer, tokenizer, out_dir, "dpo", result.metrics)
    write_run_record(out_dir, run_record, "complete", dpo_metrics=result.metrics,
                     wall_seconds=wall, peak_vram_gb=peak)
    print(f"adapter saved to {out_dir}")

    if args.export:
        import gc
        del trainer, model, dpo_ds
        gc.collect()
        torch.cuda.empty_cache()
        export(args, out_dir)
    return 0


# ---------------------------------------------------------------- export --

def export(args, adapter_dir: Path) -> None:
    """Merge the LoRA into the base in bf16, save the merged HF model, then
    try llama.cpp's convert_hf_to_gguf.py if one is anywhere on this box.
    Never fakes a GGUF: if the converter is missing, this says so and stops
    with the merged HF model already on disk."""
    import torch
    from transformers import AutoModelForCausalLM
    from peft import PeftModel

    merged_dir = adapter_dir.parent / (adapter_dir.name + "-merged")
    print(f"[export] reloading {args.model} in bf16 (full precision, not 4-bit) to merge into")
    base = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map={"": 0})
    merged = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = merged.merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    tok = load_tokenizer(str(adapter_dir))
    tok.save_pretrained(str(merged_dir))
    print(f"[export] merged bf16 model saved to {merged_dir}")

    convert_script = _find_llama_cpp_convert()
    if convert_script is None:
        print("[export] MISSING: no llama.cpp convert_hf_to_gguf.py (or "
              "convert-hf-to-gguf.py) found on this box (checked $SRLM_LLAMA_CPP, "
              "~/llama.cpp, $HOME/llama.cpp, and PATH). GGUF conversion "
              "was NOT run and no GGUF file was written. To convert: "
              "git clone --depth 1 https://github.com/ggml-org/llama.cpp somewhere, "
              "then rerun with SRLM_LLAMA_CPP=<that path> loop_train.py --export "
              "(the merged HF model above is already what it would convert).")
        return

    out_gguf = merged_dir / "model-f16.gguf"
    print(f"[export] found converter: {convert_script}")
    cmd = [sys.executable, str(convert_script), str(merged_dir),
           "--outfile", str(out_gguf), "--outtype", "f16"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out_gguf.exists():
        print(f"[export] GGUF conversion FAILED (exit {r.returncode}); merged HF "
              f"model remains at {merged_dir}. stderr tail:\n{r.stderr[-2000:]}")
        return
    print(f"[export] GGUF written to {out_gguf}")


def _find_llama_cpp_convert() -> Path | None:
    names = ("convert_hf_to_gguf.py", "convert-hf-to-gguf.py")
    candidates = []
    env = os.environ.get("SRLM_LLAMA_CPP")
    if env:
        candidates.append(Path(env))
    candidates += [Path.home() / "llama.cpp", HERE.parent / "llama.cpp"]
    for base in candidates:
        for n in names:
            p = base / n
            if p.exists():
                return p
    for p in os.environ.get("PATH", "").split(os.pathsep):
        for n in names:
            cand = Path(p) / n
            if cand.exists():
                return cand
    return None


if __name__ == "__main__":
    raise SystemExit(main())
