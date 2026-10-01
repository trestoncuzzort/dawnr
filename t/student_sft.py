#!/usr/bin/env python3
"""t/student_sft.py -- supervised fine-tuning of a pretrained student on what the gate admits
(2026-10-01).

    ~/.venv-t/bin/python t/student_sft.py --model Qwen/Qwen3.5-4B --sft sft-graded-k1.jsonl \\
        --out t/out/student/qwen35-4b-k1 [--epochs 5] [--max-len 4096]

Two published recipes, neither ours:

  the data is SAFE's (arXiv:2410.15756): only answers a verifier accepted, with the specification
  filtered by tests, fine-tuned for five epochs; t/graded_pool.py builds the rows and records each
  row's trust level;

  the fine-tuning is QLoRA's (arXiv:2305.14314, appendix B.2 and table 9): the base in 4-bit NF4
  with double quantisation and bf16 compute, LoRA r 64, alpha 16, dropout 0.1 on all linear layers
  of the transformer blocks, a constant learning rate of 2e-4, Adam beta2 0.999, gradient norm
  clipped at 0.3, batches of 16, and the loss on the response only (B.3: "only training on the
  target is beneficial"). QLoRA also groups rows by length inside a batch; here a batch is one row
  with sixteen accumulated, so there is nothing to group (and transformers 5 dropped the option).

The seed is set before the adapter is created. In TRL's trainers the adapter is initialised before
the seed is set, so two runs of one configuration start from different adapters (the operator's
own measurement, "Automated Oracles Are Not Enough", Study Design); here nothing random happens
before set_seed.

The prompt is the row's recorded system and user messages under the model's own chat template with
thinking off (a template without that switch ignores it); the response is the row's fenced answer
followed by the tokenizer's end token. A row longer than --max-len is dropped and counted, never
truncated: half an answer teaches the wrong thing.

This is separate from t/loop_train.py (DPO over preference pairs at 5e-6), which is kept as it is.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render_prompt(tokenizer, messages: list[dict]) -> str:
    """The generation prompt the served model will see: its own template, thinking off."""
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False)


def encode_row(tokenizer, row: dict, max_len: int) -> dict | None:
    """input_ids and labels for one row, the loss on the response only; None when it does not fit."""
    prompt_ids = tokenizer(render_prompt(tokenizer, row["prompt"]), add_special_tokens=False)["input_ids"]
    answer = row["chosen"] + (tokenizer.eos_token or "")
    answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
    if len(prompt_ids) + len(answer_ids) > max_len:
        return None
    return {"input_ids": prompt_ids + answer_ids,
            "labels": [-100] * len(prompt_ids) + answer_ids}


def response_loss(base, batch: dict):
    """Cross-entropy on the response tokens, with the output layer applied ONLY at the positions
    that predict them. The standard forward builds logits for every position: with a 248,320-word
    vocabulary one 2,845-token row is 2.6 GiB of logits and ended the 4B and 9B runs on a 16 GB
    card (2026-10-01), though the loss reads only the response. `base.model` is the backbone and
    `base.lm_head` the output layer (measured equal to the model's own logits, to 0.0, on
    Qwen3.5-2B); a base without those two names takes the standard forward."""
    import torch
    labels = batch["labels"]
    if not (hasattr(base, "model") and hasattr(base, "lm_head")):
        return base(**batch).loss
    hidden = base.model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).last_hidden_state
    predicts = labels[:, 1:] != -100                            # position i predicts token i + 1
    logits = base.lm_head(hidden[:, :-1][predicts])
    return torch.nn.functional.cross_entropy(logits.float(), labels[:, 1:][predicts])


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for n, r in enumerate(rows):
        if not isinstance(r.get("prompt"), list) or not isinstance(r.get("chosen"), str) or not r["chosen"].strip():
            raise SystemExit(f"{path}: row {n} has no prompt messages or no answer")
    return rows


def pad_batch(features: list[dict], pad_id: int) -> dict:
    import torch
    width = max(len(f["input_ids"]) for f in features)
    ids = torch.full((len(features), width), pad_id, dtype=torch.long)
    labels = torch.full((len(features), width), -100, dtype=torch.long)
    mask = torch.zeros((len(features), width), dtype=torch.long)
    for i, f in enumerate(features):
        n = len(f["input_ids"])
        ids[i, :n] = torch.tensor(f["input_ids"])
        labels[i, :n] = torch.tensor(f["labels"])
        mask[i, :n] = 1
    return {"input_ids": ids, "labels": labels, "attention_mask": mask}


def merge(adapter: Path, out: Path) -> int:
    """The adapter folded into its full-precision base and saved as one model, the form that is
    served and later converted for release (peft's merge_and_unload, as t/loop_train.py's export
    does: in bf16 against the unquantised base, never the 4-bit one)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    base_id = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))["base_model_name_or_path"]
    base = AutoModelForCausalLM.from_pretrained(base_id, dtype=torch.bfloat16, device_map={"": 0})
    merged = PeftModel.from_pretrained(base, str(adapter)).merge_and_unload()
    out.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(out))
    AutoTokenizer.from_pretrained(str(adapter)).save_pretrained(str(out))
    (out / "merged-from.json").write_text(json.dumps({"base": base_id, "adapter": str(adapter)}, indent=1) + "\n",
                                          encoding="utf-8")
    print(f"merged {adapter} into {base_id}: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="the base's hub id or a local directory")
    ap.add_argument("--sft", type=Path, help="t/graded_pool.py rows (prompt, chosen)")
    ap.add_argument("--merge", type=Path, metavar="ADAPTER",
                    help="instead of training: fold this adapter into its base and save the model to --out")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=5.0, help="SAFE trains five epochs a round")
    ap.add_argument("--lr", type=float, default=2e-4, help="QLoRA table 9 (7B, 13B)")
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--alpha", type=int, default=16)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16, help="batch x grad-accum is QLoRA's 16")
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="first N rows only (a smoke run)")
    ap.add_argument("--warmup-steps", type=int, default=0,
                    help="linear warm-up of the learning rate over the first N optimizer steps (default 0: "
                         "QLoRA's constant rate from the first step)")
    ap.add_argument("--max-steps", type=int, default=0, help="stop after N optimizer steps (a stability probe)")
    ap.add_argument("--log-every", type=int, default=5, help="log the loss every N optimizer steps")
    a = ap.parse_args(argv)
    if a.merge:
        return merge(a.merge, a.out)
    if not a.model or not a.sft:
        ap.error("--model and --sft are required to train")

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer,
                              TrainingArguments, set_seed)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    set_seed(a.seed)                                            # before anything random, the adapter included
    rows = load_rows(a.sft)
    if a.limit:
        rows = rows[: a.limit]
    tokenizer = AutoTokenizer.from_pretrained(a.model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    encoded, dropped = [], 0
    for r in rows:
        e = encode_row(tokenizer, r, a.max_len)
        if e is None:
            dropped += 1
        else:
            encoded.append(e)
    if not encoded:
        raise SystemExit("student_sft: no row fits --max-len")
    lengths = sorted(len(e["input_ids"]) for e in encoded)
    print(f"rows: {len(encoded)} used, {dropped} dropped as longer than {a.max_len} tokens; "
          f"tokens per row median {lengths[len(lengths) // 2]}, longest {lengths[-1]}", flush=True)

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=quant, device_map={"": 0})
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=a.dropout, bias="none",
                                             target_modules="all-linear", task_type="CAUSAL_LM"))
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"trainable parameters: {trainable:,}", flush=True)

    a.out.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(a.out / "trainer"), per_device_train_batch_size=a.batch,
        gradient_accumulation_steps=a.grad_accum, num_train_epochs=a.epochs, learning_rate=a.lr,
        lr_scheduler_type="constant_with_warmup" if a.warmup_steps else "constant",
        warmup_steps=a.warmup_steps, max_steps=a.max_steps or -1,
        adam_beta2=0.999, max_grad_norm=0.3, bf16=True,
        optim="paged_adamw_32bit", logging_steps=a.log_every, save_strategy="no",
        report_to=[], seed=a.seed, data_seed=a.seed, remove_unused_columns=False)

    class Rows(torch.utils.data.Dataset):
        def __len__(self):
            return len(encoded)

        def __getitem__(self, i):
            return encoded[i]

    class ResponseOnly(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **_kw):
            base = model.get_base_model() if hasattr(model, "get_base_model") else model
            loss = response_loss(base, inputs)
            return (loss, None) if return_outputs else loss

    trainer = ResponseOnly(model=model, args=args, train_dataset=Rows(),
                           data_collator=lambda fs: pad_batch(fs, tokenizer.pad_token_id))
    started = time.time()
    result = trainer.train()
    seconds = round(time.time() - started, 1)
    model.save_pretrained(str(a.out))
    tokenizer.save_pretrained(str(a.out))
    record = {"schema": 1, "base": a.model, "sft": str(a.sft),
              "sft_sha256": hashlib.sha256(a.sft.read_bytes()).hexdigest(),
              "rows_used": len(encoded), "rows_dropped_too_long": dropped,
              "recipe": {"quantisation": "nf4, double, bf16 compute", "lora": {"r": a.rank, "alpha": a.alpha,
                         "dropout": a.dropout, "target_modules": "all-linear"},
                         "lr": a.lr, "schedule": "constant", "adam_beta2": 0.999, "max_grad_norm": 0.3,
                         "warmup_steps": a.warmup_steps, "max_steps": a.max_steps or None,
                         "batch": a.batch, "grad_accum": a.grad_accum, "epochs": a.epochs,
                         "max_len": a.max_len, "seed": a.seed, "loss": "response only",
                         "sources": ["arXiv:2305.14314 B.2, table 9", "arXiv:2410.15756 C.3"]},
              "trainable_parameters": trainable, "train_loss": result.training_loss,
              "steps": result.global_step, "seconds": seconds,
              "log": [h for h in trainer.state.log_history if "loss" in h],
              "versions": {"torch": torch.__version__,
                           "transformers": __import__("transformers").__version__,
                           "peft": __import__("peft").__version__}}
    (a.out / "run.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"done: {result.global_step} steps, train loss {result.training_loss:.4f}, {seconds} s; adapter in {a.out}")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
