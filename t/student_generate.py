#!/usr/bin/env python3
"""t/student_generate.py -- a student's answers, decoded in batches on this machine (2026-10-01).

    ~/.venv-t/bin/python t/student_generate.py --model DIR --tag-prefix student-x --seeds 1 2 3 4 \\
        --pool v5 --prompt s1 --ids-file ids.txt --temperature 0.8

Writes the same raw records t/spec_experiment.py generate writes (one answer set per seed, named
<tag-prefix>-s<seed>, or exactly --tag for a single greedy set), so extract, tests, the kernels,
the specification check and every scorer read them unchanged. The difference is the decoder: the
model is loaded once with transformers and each batch of problems is decoded together with left
padding, where the server path answers one request at a time (4.4 s an answer on a 2B student;
several answers per problem, SAFE's Accuracy@10, are not affordable that way).

The prompt is spec_experiment.build_prompt's under the model's own chat template with thinking
off, which is what t/student_sft.py trained on. Sampling is seeded per (seed, problem), so a
problem's answer does not depend on which batch it fell in or on a resume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402
import student_sft                                              # noqa: E402


def problem_seed(seed: int, tid: str) -> int:
    return int(hashlib.sha256(f"{seed}:{tid}".encode()).hexdigest()[:8], 16)


def load(model_dir: str):
    """(model, tokenizer) for batched decoding: bf16 on the card, left padding."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.bfloat16, device_map={"": 0})
    model.eval()
    return model, tokenizer


def decode(model, tokenizer, conversations: list[list[dict]], max_new: int, temperature: float = 0.0,
           top_p: float = 0.95, seed: int | None = None) -> list[tuple[str, bool, int]]:
    """One reply per conversation, decoded as one batch: (text, stopped at the end token, tokens)."""
    import torch
    prompts = [student_sft.render_prompt(tokenizer, m) for m in conversations]
    enc = tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
    with torch.no_grad():
        if temperature > 0:
            if seed is not None:
                torch.manual_seed(seed)
            out = model.generate(**enc, max_new_tokens=max_new, do_sample=True, temperature=temperature,
                                 top_p=top_p, top_k=0, pad_token_id=tokenizer.pad_token_id)
        else:
            out = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tokenizer.pad_token_id)
    replies = []
    for row in out[:, enc["input_ids"].shape[1]:]:
        tokens = [int(x) for x in row if int(x) != tokenizer.pad_token_id]
        stopped = tokenizer.eos_token_id in tokens
        if stopped:
            tokens = tokens[: tokens.index(tokenizer.eos_token_id)]
        replies.append((tokenizer.decode(tokens, skip_special_tokens=True), stopped, len(tokens)))
    return replies


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="a merged model directory or a hub id")
    ap.add_argument("--tag", default="", help="one answer set with this exact name (single seed)")
    ap.add_argument("--tag-prefix", default="", help="answer sets named <prefix>-s<seed>")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--prompt", choices=se.PROMPT_VERSIONS, default="s1")
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args(argv)
    if bool(a.tag) == bool(a.tag_prefix):
        ap.error("give exactly one of --tag and --tag-prefix")
    if a.tag and len(a.seeds) != 1:
        ap.error("--tag names one answer set; use --tag-prefix for several seeds")

    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [line.strip() for line in a.ids_file.read_text(encoding="utf-8").split() if line.strip()]
    missing = [t for t in ids if t not in P]
    if missing:
        raise SystemExit(f"student_generate: ids not in pool {a.pool}: {missing[:5]}")

    model, tokenizer = load(a.model)
    digest = hashlib.sha256(json.dumps(sorted(str(p.name) for p in Path(a.model).glob("*.safetensors"))
                                       if Path(a.model).is_dir() else a.model).encode()).hexdigest()[:12]

    for seed in a.seeds:
        tag = a.tag or f"{a.tag_prefix}-s{seed}"
        d = se.outdir(tag)
        lock = se.tag_lock(d)
        if lock is None:
            print(f"student_generate: another generator holds {tag}; skipped", file=sys.stderr)
            continue
        options = {"temperature": a.temperature, "seed": seed, "num_predict": a.max_new,
                   "top_p": a.top_p if a.temperature > 0 else None, "decoder": "transformers-batched",
                   "seeding": "per-problem"}
        todo = [t for t in ids if not (d / "raw" / f"{t}.json").exists()]
        started = time.monotonic()
        for start in range(0, len(todo), a.batch):
            chunk = todo[start:start + a.batch]
            messages = [se.build_prompt(P[t], a.prompt) for t in chunk]
            # sampling is seeded per batch from its first problem: a resumed run is identical as
            # long as batches start at the same problems, which the fixed order and size guarantee
            replies = decode(model, tokenizer, messages, a.max_new, a.temperature, a.top_p,
                             problem_seed(seed, chunk[0]))
            for tid, msg, (text, stopped, ntok) in zip(chunk, messages, replies):
                record = {"task_id": tid, "fn": P[tid]["fn"], "model": str(a.model), "digest": digest,
                          "pool_version": a.pool, "prompt_version": a.prompt, "options": options,
                          "messages": msg, "reply": text,
                          "reply_tokens": ntok, "done_reason": "stop" if stopped else "length"}
                se.write_record(d / "raw" / f"{tid}.json", record)
            done = min(start + a.batch, len(todo))
            print(f"student_generate: {tag}: {done}/{len(todo)} ({time.monotonic() - started:.0f} s)", flush=True)
        lock.close()
        print(f"student_generate: {tag}: {len(ids)} problems have a reply on disk", flush=True)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
