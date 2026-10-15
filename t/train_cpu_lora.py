#!/usr/bin/env python3
"""E3 CPU LoRA SFT trainer -- no GPU, no 4-bit (student_sft.py's training path is QLoRA/bitsandbytes = GPU
only; its --cpu is merge-only). Loads a permissive base in fp32 on CPU, applies LoRA (arXiv:2106.09685:
frozen base + low-rank adapters, no quantization/hardware precondition), and fine-tunes on one arm's
(prompt, chosen) rows, subsampled to a matched budget with a fixed seed. Deterministic per seed.

    python3 train_cpu_lora.py --base <hub-id-or-dir> --arm arm-all7.jsonl --seed 0 --max-rows 117 --out <dir>
"""
import argparse
import json
import pathlib
import random

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, set_seed


def load_arm(path, seed, max_rows):
    rows = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    random.Random(seed).shuffle(rows)
    if max_rows and len(rows) > max_rows:
        rows = rows[:max_rows]       # matched budget: same row count across arms, seeded
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-rows", type=int, default=117)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--maxlen", type=int, default=1024)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    set_seed(a.seed)

    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    rows = load_arm(a.arm, a.seed, a.max_rows)

    def tokenize(r):
        msgs = r["prompt"] if isinstance(r["prompt"], list) else [{"role": "user", "content": str(r["prompt"])}]
        prompt_text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        p_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]
        c_ids = tok(r["chosen"] + tok.eos_token, add_special_tokens=False)["input_ids"]
        # SFT loss on the completion only: ALWAYS keep the whole completion; truncate the (long, few-shot)
        # prompt from the LEFT to fit maxlen, so labels are never all-masked (which gave loss 0).
        c_ids = c_ids[:a.maxlen]
        budget = a.maxlen - len(c_ids)
        p_ids = p_ids[-budget:] if budget > 0 else []
        input_ids = p_ids + c_ids
        labels = [-100] * len(p_ids) + c_ids
        return {"input_ids": input_ids, "labels": labels, "attention_mask": [1] * len(input_ids)}

    base_ds = Dataset.from_list(rows)
    ds = base_ds.map(tokenize, remove_columns=base_ds.column_names)

    def collate(batch):
        m = max(len(b["input_ids"]) for b in batch)
        pad = tok.pad_token_id
        out = {"input_ids": [], "labels": [], "attention_mask": []}
        for b in batch:
            n = m - len(b["input_ids"])
            out["input_ids"].append(b["input_ids"] + [pad] * n)
            out["labels"].append(b["labels"] + [-100] * n)
            out["attention_mask"].append(b["attention_mask"] + [0] * n)
        return {k: torch.tensor(v) for k, v in out.items()}

    base = AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.float32, device_map={"": "cpu"})
    base.config.use_cache = False
    model = get_peft_model(base, LoraConfig(
        r=a.rank, lora_alpha=a.rank * 2, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()
    args = TrainingArguments(
        output_dir=str(pathlib.Path(a.out) / "trainer"), per_device_train_batch_size=1,
        gradient_accumulation_steps=16, num_train_epochs=a.epochs, learning_rate=a.lr,
        lr_scheduler_type="constant", logging_steps=2, save_strategy="no", seed=a.seed,
        use_cpu=True, report_to=[], dataloader_num_workers=0)
    Trainer(model=model, args=args, train_dataset=ds, data_collator=collate).train()
    outd = pathlib.Path(a.out); outd.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(outd)); tok.save_pretrained(str(outd))
    (outd / "train-meta.json").write_text(json.dumps(
        {"base": a.base, "arm": a.arm, "seed": a.seed, "rows": len(rows),
         "distinct_tasks": len({r.get("task") for r in rows}), "epochs": a.epochs, "lr": a.lr, "rank": a.rank}, indent=1))
    print(f"TRAINED arm={pathlib.Path(a.arm).stem} seed={a.seed} rows={len(rows)} -> {outd}")


if __name__ == "__main__":
    main()
