#!/usr/bin/env python3
"""E3 trainer (CPU LoRA). Fine-tune a small permissive base on one arm's rows and save a merged model.

No GPU is available (AWS Free Tier blocks paid instances; lab GPUs closed; desktop unreachable), so
this uses plain LoRA in fp32 on the lab's CPUs instead of QLoRA — valid for the matched ablation, which
is a relative comparison across arms at one budget. Each arm row is {prompt:[messages], chosen:<t prog>}.

    ~/e3-venv/bin/python train_lora_cpu.py --base <hub-id> --arm arm.jsonl --seed 0 --out <dir> [--epochs 5]
"""
import argparse, json, os, random, collections, sys
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
sys.path.insert(0, ".")
import e3_base

torch.set_num_threads(int(os.environ.get("E3_THREADS", "12")))


def budget_select(rows, tok, maxlen, budget):
    """Consume rows in a FIXED per-task round-robin (tasks sorted, rows sorted within task) until the
    cumulative supervised-token budget is reached, so every arm/seed trains to the SAME effective budget
    and the dropped tail is spread across tasks (diversity preserved), not concentrated in one task.
    budget<=0 keeps all rows. Returns (selected_rows, realized_stats)."""
    if not budget or budget <= 0:
        return rows, {"max_supervised_tokens": 0, "realized_supervised_tokens": None, "rows_used": len(rows),
                      "rows_total": len(rows), "note": "no budget cap (used all rows)"}
    by = collections.defaultdict(list)
    for r in rows:
        by[r.get("task", "")].append(r)
    order = []
    for t in by:
        by[t] = sorted(by[t], key=lambda z: z.get("chosen", ""))
    ptr = {t: 0 for t in by}; tasks = sorted(by)
    progressed = True
    while progressed:                                                 # round-robin flatten (deterministic)
        progressed = False
        for t in tasks:
            if ptr[t] < len(by[t]):
                order.append(by[t][ptr[t]]); ptr[t] += 1; progressed = True
    picked, used = [], 0
    for r in order:
        sup = encode_row(r, tok, maxlen)["n_supervised"]
        if sup < 1:
            continue
        if used + sup > budget:
            continue                                                  # skip; a shorter later row may still fit
        picked.append(r); used += sup
    return picked, {"max_supervised_tokens": budget, "realized_supervised_tokens": used,
                    "rows_used": len(picked), "rows_total": len(rows)}


def compact_prompt(msgs, task):
    """A short, constant-format prompt: the task only (drop the big few-shot preamble so training is
    fast and the completion is never truncated away). The last user turn carries the task."""
    user = ""
    for m in (msgs or []):
        if m.get("role") == "user":
            user = m.get("content", "")
    # the task spec is the tail of the last user turn; keep its last ~1500 chars
    user = user[-1500:] if user else task
    return [{"role": "system", "content": "Write a t program for the task."},
            {"role": "user", "content": user}]


def encode_row(r, tok, maxlen=768):
    """THE single training-preprocessing path. Returns the exact tokens training consumes plus an audit:
    compact prompt -> tokenize -> left-truncate the prompt to fit maxlen while keeping the FULL completion.
    Used by both SFT (training) and the token-budget matcher (audit), so the audit can never drift from
    what the trainer actually sees."""
    msgs = compact_prompt(r.get("prompt"), r.get("task", ""))
    try:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        text = "\n".join(m.get("content", "") for m in msgs) + "\n"
    prompt_full = tok(text, add_special_tokens=False)["input_ids"]
    comp_ids = tok((r.get("chosen") or "") + tok.eos_token, add_special_tokens=False)["input_ids"]
    keep = max(0, maxlen - len(comp_ids))
    prompt_ids = (prompt_full[-keep:] if keep else []) if keep < len(prompt_full) else prompt_full
    ids = prompt_ids + comp_ids
    labels = [-100] * len(prompt_ids) + comp_ids
    dropped = len(prompt_full) - len(prompt_ids)
    return {"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids),
            "n_input": len(ids), "n_supervised": len(comp_ids), "n_prompt_full": len(prompt_full),
            "n_prompt_kept": len(prompt_ids), "prompt_dropped": dropped, "truncated": dropped > 0}


class SFT(Dataset):
    def __init__(self, rows, tok, maxlen=768):
        self.ex = []
        for r in rows:
            e = encode_row(r, tok, maxlen)
            if sum(1 for x in e["labels"] if x != -100) < 1:
                continue
            self.ex.append({k: e[k] for k in ("input_ids", "labels", "attention_mask")})

    def __len__(self):
        return len(self.ex)

    def __getitem__(self, i):
        return self.ex[i]


def collate(batch, pad_id):
    m = max(len(b["input_ids"]) for b in batch)
    def pad(x, v):
        return x + [v] * (m - len(x))
    import torch as T
    return {"input_ids": T.tensor([pad(b["input_ids"], pad_id) for b in batch]),
            "attention_mask": T.tensor([pad(b["attention_mask"], 0) for b in batch]),
            "labels": T.tensor([pad(b["labels"], -100) for b in batch])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=e3_base.BASE)
    ap.add_argument("--rev", default=e3_base.REV)                      # PINNED revision (same as matcher/generator)
    ap.add_argument("--arm", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--epochs", type=float, default=5.0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-supervised-tokens", type=int, default=0,
                    help="matched effective training budget (from train_budget.json); 0 = use all rows")
    ap.add_argument("--max-nonfinite-frac", type=float, default=0.25)  # abort if too many batches are nonfinite
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed)
    rev = a.rev if (a.base == e3_base.BASE) else None                 # only pin a hub id we know the sha for
    print(f"E3-TRAINER v3 (base={a.base} rev={str(rev)[:8]} lr={a.lr} clip=on nan-skip=on "
          f"budget={a.max_supervised_tokens}) arm={a.arm.name} seed={a.seed} epochs={a.epochs}", flush=True)

    rows = [json.loads(l) for l in a.arm.read_text().splitlines() if l.strip()]
    tok = AutoTokenizer.from_pretrained(a.base, revision=rev)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    rows, bsel = budget_select(rows, tok, 768, a.max_supervised_tokens)
    print(f"budget-select: {bsel}", flush=True)
    model = AutoModelForCausalLM.from_pretrained(a.base, revision=rev, torch_dtype=torch.float32)
    model.config.use_cache = False
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    ds = SFT(rows, tok)
    print(f"arm {a.arm.name} seed {a.seed}: {len(ds)} examples", flush=True)
    if len(ds) == 0:
        print("FATAL: 0 supervised examples after preprocessing; refusing to save a model", flush=True); sys.exit(6)
    # manual training loop (robust to TrainingArguments API drift); batch 1, grad-accum ACCUM
    from torch.optim import AdamW
    opt = AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr)
    model.train()
    idx = list(range(len(ds)))
    accum = e3_base.ACCUM
    step = 0
    import math
    total_batches = nonfinite_batches = 0
    for epoch in range(int(a.epochs)):
        random.Random(a.seed + epoch).shuffle(idx)
        opt.zero_grad(); pending = 0
        last = float("nan")
        for bi, j in enumerate(idx):
            b = collate([ds[j]], tok.pad_token_id)
            out = model(**b)
            lv = out.loss.item(); total_batches += 1
            if not math.isfinite(lv):
                nonfinite_batches += 1
                opt.zero_grad(); pending = 0      # drop this window, don't poison grads
                continue
            last = lv
            (out.loss / accum).backward(); pending += 1
            if pending == accum:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step(); opt.zero_grad(); step += 1; pending = 0
                if step % 5 == 0:
                    print(f"epoch {epoch} step {step} loss {lv:.3f}", flush=True)
        if pending:                                # flush a partial window only if it holds real grads
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step(); opt.zero_grad(); step += 1
        print(f"epoch {epoch} done (last finite loss {last:.3f})", flush=True)
    nf_frac = nonfinite_batches / max(1, total_batches)
    print(f"optimizer updates={step} nonfinite_batches={nonfinite_batches}/{total_batches} ({nf_frac:.1%})", flush=True)
    if step == 0:
        print("FATAL: 0 optimizer updates (no finite batches); refusing to save a model", flush=True); sys.exit(7)
    if nf_frac > a.max_nonfinite_frac:
        print(f"FATAL: nonfinite fraction {nf_frac:.1%} > {a.max_nonfinite_frac:.0%}; training unstable, "
              f"refusing to save a model", flush=True); sys.exit(8)
    # merge adapter into base and save a standalone model for generation
    merged = model.merge_and_unload()
    (a.out).mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(a.out / "merged")
    tok.save_pretrained(a.out / "merged")
    (a.out / "train-manifest.json").write_text(json.dumps(
        {"base": a.base, "revision": rev, "arm": a.arm.name, "seed": a.seed, "epochs": a.epochs, "lr": a.lr,
         "accum": accum, "examples": len(ds), "optimizer_updates": step,
         "nonfinite_batches": nonfinite_batches, "total_batches": total_batches,
         "budget_select": bsel}, indent=2), encoding="utf-8")
    print(f"saved merged model -> {a.out/'merged'} (manifest: train-manifest.json)", flush=True)


if __name__ == "__main__":
    main()
