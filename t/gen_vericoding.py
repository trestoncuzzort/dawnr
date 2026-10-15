#!/usr/bin/env python3
"""E3 Vericoding eval generation (CPU). A merged student writes a t program for each held-out Vericoding
spec (rendered by surface.print_task with the body stripped), k samples per problem (sample 0 greedy for
pass@1, the rest sampled for pass@k). Replies go to a JSONL that grade.py --replies then grades by the gate
(real verified + one-edit twin refuted). Vericoding is disjoint from the MBPP arm-train tasks.

    ~/.venv-e3/bin/python gen_vericoding.py --model <merged> --tag <t> --limit 16 --samples 5 --out <dir>
"""
import argparse
import glob
import json
import pathlib
import re
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

sys.path.insert(0, ".")
import surface      # noqa: E402
import tasks_io     # noqa: E402


def spec_prompt(task):
    src = surface.print_task(task)
    spec = src.split("\n{", 1)[0].rstrip()        # drop the body block; keep signature + requires/ensures + spec funs
    return [{"role": "system", "content": "Write a t program for the task."},
            {"role": "user", "content": spec}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--corpus", default="vericoding/dafny")
    ap.add_argument("--limit", type=int, default=16)
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--max-new", type=int, default=320)
    ap.add_argument("--include-recursion", action="store_true", help="by default skip gate==recursion (harder) tasks")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.float32, device_map={"": "cpu"})
    model.eval()
    files = sorted(glob.glob(a.corpus + "/*.json"))
    picked, tasks = [], []
    for f in files:
        try:
            t = tasks_io.load_task(f)
            if (not a.include_recursion) and t.get("gate") == "recursion":
                continue
            spec_prompt(t)
            tasks.append((pathlib.Path(f).stem, t))
            if len(tasks) >= a.limit:
                break
        except Exception:  # noqa: BLE001
            continue
    outd = pathlib.Path(a.out); outd.mkdir(parents=True, exist_ok=True)
    rep_path = outd / "replies.jsonl"
    n = 0
    with rep_path.open("w", encoding="utf-8") as fh:
        for idx, (name, t) in enumerate(tasks):
            msgs = spec_prompt(t)
            text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            enc = tok(text, return_tensors="pt")
            for s in range(a.samples):
                set_seed(a.seed * 1000 + s)
                with torch.no_grad():
                    kw = dict(max_new_tokens=a.max_new, pad_token_id=tok.pad_token_id or tok.eos_token_id)
                    if s == 0:
                        out = model.generate(**enc, do_sample=False, **kw)
                    else:
                        out = model.generate(**enc, do_sample=True, temperature=a.temperature, top_p=0.95, **kw)
                reply = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                # REPLACE the model's task name with a deterministic id I control (vp<problem>_s<sample>), so
                # grade.py (which keys by the extracted program's task name) groups reliably by PROBLEM and
                # sample -- the model's own per-sample renaming no longer corrupts the pass@k grouping.
                reply = re.sub(r"(^|\n)(\s*)task\s+[A-Za-z_][A-Za-z0-9_]*",
                               lambda m: f"{m.group(1)}{m.group(2)}task vp{idx}_s{s}", reply, count=1)
                fh.write(json.dumps({"id": f"vp{idx}#s{s}", "task": name, "problem": idx, "sample": s, "reply": reply}) + "\n")
                n += 1
            print(f"  {name}: {a.samples} samples", flush=True)
    print(f"gen_vericoding {a.tag}: {len(tasks)} problems x {a.samples} = {n} replies -> {rep_path}")


if __name__ == "__main__":
    main()
