#!/usr/bin/env python3
"""E3 eval generation (CPU). A merged student writes a t program for each held-out MBPP eval problem;
the records are graded by the engine's grade.py --replies (tests + all seven kernels). Same compact
prompt as training, greedy decode. MBPP eval split is disjoint from the arms' train tasks.

    ~/e3-venv/bin/python gen_eval_cpu.py --model out/e3-runs/all7-s0/merged --tag e3eval-all7-s0 \
        --split out/loop/split-v5.json --limit 40 [--prompt s2 --pool v1 --max-new 320]
"""
import argparse, json, os, sys
from pathlib import Path
import torch

os.environ.setdefault("HF_HOME", os.path.expanduser("~/hf-cache"))
torch.set_num_threads(int(os.environ.get("E3_THREADS", "32")))
sys.path.insert(0, ".")
import spec_experiment as se           # noqa: E402
from train_lora_cpu import compact_prompt  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--prompt", default="s2")
    ap.add_argument("--pool", default="v1")
    ap.add_argument("--max-new", type=int, default=320)
    a = ap.parse_args()

    pool = se.pool(a.pool)
    eval_ids = json.load(open(a.split)).get("eval_ids", [])
    ids = [i for i in eval_ids if i in pool][: a.limit]
    print(f"{a.tag}: {len(ids)} eval problems", flush=True)

    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.float32)
    model.eval()

    outdir = se.outdir(a.tag)
    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    for n, tid in enumerate(ids, 1):
        e = pool[tid]
        msgs = compact_prompt(se.build_prompt(e, a.prompt), e["rec"].get("text", ""))
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=a.max_new, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        reply = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        rec = {"task_id": tid, "fn": e["fn"], "reply": reply,
               "pool_version": a.pool, "prompt_version": a.prompt, "messages": msgs,
               "model": a.model}
        (outdir / "raw" / f"{tid}.json").write_text(json.dumps(rec), encoding="utf-8")
        if n % 10 == 0:
            print(f"  {a.tag} {n}/{len(ids)}", flush=True)
    print(f"{a.tag}: wrote {len(ids)} raw records -> {outdir/'raw'}", flush=True)


if __name__ == "__main__":
    main()
