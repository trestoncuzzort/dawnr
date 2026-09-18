#!/usr/bin/env python3
"""loop_train.py -- QLoRA DPO on Qwen2.5-Coder-1.5B-Instruct, over the bugs
loop_dataset.py built.

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
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
DEFAULT_PAIRS = HERE / "out" / "loop" / "pairs.jsonl"
DEFAULT_SFT = HERE / "out" / "loop" / "sft.jsonl"
DEFAULT_OUT = HERE / "out" / "loop" / "adapter"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"]
MIN_FREE_MIB = 4096      # "about 3 to 4 GB" for the 1.5B in 4-bit; refuse below this


# ------------------------------------------------------------- GPU pick --

def free_vram_by_gpu() -> dict[int, int]:
    """{gpu index: free MiB}, from nvidia-smi. Never touches torch/CUDA."""
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


def build_pair_dataset(tokenizer, path: Path, max_len: int):
    from datasets import Dataset
    rows = load_jsonl(path)
    prompts, chosen, rejected = [], [], []
    for r in rows:
        p = render_prompt(tokenizer, r["prompt"])
        prompts.append(p)
        chosen.append(r["chosen"])
        rejected.append(r["rejected"])
    ds = Dataset.from_dict({"prompt": prompts, "chosen": chosen, "rejected": rejected})
    return ds


def build_sft_dataset(tokenizer, path: Path):
    from datasets import Dataset
    rows = load_jsonl(path)
    texts = []
    eos = tokenizer.eos_token or ""
    for r in rows:
        p = render_prompt(tokenizer, r["prompt"])
        texts.append(p + r["chosen"] + eos)
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
    ap.add_argument("--gpu", type=int, default=None, help="pin a GPU index; default: most free VRAM")
    ap.add_argument("--min-free-mib", type=int, default=MIN_FREE_MIB)
    ap.add_argument("--smoke", action="store_true", help="5 steps, batch 1, no --steps/--batch needed")
    ap.add_argument("--export", action="store_true",
                    help="after training: merge adapter into base (bf16), save, try GGUF")
    args = ap.parse_args()

    if args.smoke:
        args.steps = 5
        args.batch = 1
        args.grad_accum = 1
        args.max_len = min(args.max_len, 256)   # box is shared; keep the smoke footprint small

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
    # this box's other GPU users make free memory a moving target; reduce
    # fragmentation rather than assume the nvidia-smi snapshot above still
    # holds by the time the first backward pass runs.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    # ------------------------------------------------------- heavy imports
    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import DPOConfig, DPOTrainer

    dev = torch.device("cuda:0")   # index 0 WITHIN CUDA_VISIBLE_DEVICES
    torch.cuda.reset_peak_memory_stats(dev)
    t_start = time.monotonic()

    print(f"loading tokenizer + base model: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16)
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(r=16, lora_alpha=16, lora_dropout=0.0,
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

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------- optional SFT warm-up
    if args.sft_first:
        from trl import SFTConfig, SFTTrainer
        sft_path = Path(args.sft)
        print(f"SFT warm-up on {sft_path}")
        sft_ds = build_sft_dataset(tokenizer, sft_path)
        sft_wanted = dict(
            output_dir=str(out_dir / "sft-warmup"),
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            num_train_epochs=1, learning_rate=args.lr, bf16=True,
            logging_steps=1, max_steps=(5 if args.smoke else -1),
            dataset_text_field="text", max_seq_length=args.max_len,
            report_to=[])
        sft_cfg = SFTConfig(**_kwargs_for(SFTConfig, sft_wanted))
        sft_trainer_kwargs = dict(model=model, args=sft_cfg, train_dataset=sft_ds,
                                  tokenizer=tokenizer, processing_class=tokenizer)
        sft_trainer = SFTTrainer(**_kwargs_for(SFTTrainer, sft_trainer_kwargs))
        sft_trainer.train()
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
    print(f"building DPO dataset from {args.pairs}")
    dpo_ds = build_pair_dataset(tokenizer, Path(args.pairs), args.max_len)
    print(f"DPO pairs: {len(dpo_ds)}")

    dpo_wanted = dict(
        output_dir=str(out_dir), per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum, warmup_ratio=0.1,
        num_train_epochs=args.epochs, max_steps=(args.steps or -1),
        learning_rate=args.lr, beta=0.1, bf16=True, optim="paged_adamw_8bit",
        # The recorded prompt (grammar, five examples, the problem) is about
        # 1,600 Qwen tokens, so the prompt budget is the whole window minus
        # 512 for the answer; a half-window prompt budget would truncate the
        # grammar away. use_logits_to_keep computes logits for the
        # completion tokens only: the full-window, full-vocabulary fp32
        # logits (2048 x 152k x 4 bytes, twice for chosen and rejected) are
        # what put the first run out of memory on a 4.8 GB slice of a
        # shared card (measured 2026-09-09).
        logging_steps=1, max_length=args.max_len,
        max_prompt_length=max(args.max_len - 512, args.max_len // 2),
        use_logits_to_keep=True,
        # trl 1.13 has neither of the two above; what it does have is a reference pass computed once, up front,
        # instead of beside the policy's own graph, which is the larger of the two costs on a 16 GB card
        precompute_ref_log_probs=True,
        # the activations of a 3,300-token pair, recomputed rather than kept: the card is 200 MB short of the
        # 1.84 GiB logits tensor without this, measured 2026-09-18
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        # every pair is padded to max_length otherwise, and the median pair is 2,895 tokens against a 3,328
        # window, so a fifth of the logits tensor is padding the card pays bf16 for
        padding_free=True,
        report_to=[])
    dpo_cfg = DPOConfig(**_kwargs_for(DPOConfig, dpo_wanted))

    dpo_trainer_kwargs = dict(model=model, args=dpo_cfg, train_dataset=dpo_ds,
                              tokenizer=tokenizer, processing_class=tokenizer,
                              max_length=args.max_len, max_prompt_length=args.max_len // 2)
    trainer = DPOTrainer(**_kwargs_for(DPOTrainer, dpo_trainer_kwargs))

    print(f"training: steps={args.steps} epochs={args.epochs} lr={args.lr} "
          f"batch={args.batch} grad_accum={args.grad_accum} max_len={args.max_len}")
    result = trainer.train()

    wall = time.monotonic() - t_start
    peak = torch.cuda.max_memory_allocated(dev) / 1e9
    print(f"trained: {result}")
    print(f"peak VRAM: {peak:.2f} GB")
    print(f"wall time: {wall:.1f} s")
    print(f"GPU used: {gpu}")

    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"adapter saved to {out_dir}")

    if args.export:
        export(args, out_dir)
    return 0


# ---------------------------------------------------------------- export --

def export(args, adapter_dir: Path) -> None:
    """Merge the LoRA into the base in bf16, save the merged HF model, then
    try llama.cpp's convert_hf_to_gguf.py if one is anywhere on this box.
    Never fakes a GGUF: if the converter is missing, this says so and stops
    with the merged HF model already on disk."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    merged_dir = adapter_dir.parent / (adapter_dir.name + "-merged")
    print(f"[export] reloading {args.model} in bf16 (full precision, not 4-bit) to merge into")
    base = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map={"": 0})
    merged = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = merged.merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(merged_dir), safe_serialization=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    tok.save_pretrained(str(merged_dir))
    print(f"[export] merged bf16 model saved to {merged_dir}")

    convert_script = _find_llama_cpp_convert()
    if convert_script is None:
        print("[export] MISSING: no llama.cpp convert_hf_to_gguf.py (or "
              "convert-hf-to-gguf.py) found on this box (checked $SRLM_LLAMA_CPP, "
              "~/llama.cpp, /home/tmcuzzort/llama.cpp, and PATH). GGUF conversion "
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
