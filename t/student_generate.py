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


def load(model_dir: str, device: str | None = None):
    """(model, tokenizer) for decoding, left padding. On the card in bf16 by default; with
    device "cpu" (or no card visible) in fp32, which is slow and is for checking the plumbing."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.float32)
    else:
        model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.bfloat16, device_map={"": 0})
    model.eval()
    return model, tokenizer


def decode(model, tokenizer, conversations: list[list[dict]], max_new: int, temperature: float = 0.0,
           top_p: float = 0.95, seed: int | None = None, generate_batch=None) -> list[tuple[str, bool, int]]:
    """One reply per conversation: (text, stopped at the end token, tokens). Decoded as one batch; a batch that
    runs the card out of memory is split in half and each half decoded again (the halving of accelerate's
    find_executable_batch_size, github.com/huggingface/accelerate utils/memory.py: free the cache, try a smaller
    batch). A single conversation that still does not fit gets an empty reply, counted as no answer, so one
    oversized prompt cannot end a run that has hours of answers in memory."""
    run = generate_batch or _generate_batch
    try:
        return run(model, tokenizer, conversations, max_new, temperature, top_p, seed)
    except Exception as e:                                      # noqa: BLE001
        if " out of memory." not in str(e):                     # accelerate's should_reduce_batch_size test
            raise
        _free_cache()
        if len(conversations) == 1:
            print(f"student_generate: one prompt does not fit on the card; no answer for it", file=sys.stderr, flush=True)
            return [("", False, 0)]
        half = len(conversations) // 2
        second = None if seed is None else seed + 1
        print(f"student_generate: out of memory at batch {len(conversations)}; halves of {half} and "
              f"{len(conversations) - half}", file=sys.stderr, flush=True)
        return (decode(model, tokenizer, conversations[:half], max_new, temperature, top_p, seed, run)
                + decode(model, tokenizer, conversations[half:], max_new, temperature, top_p, second, run))


def _free_cache() -> None:
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:                                            # noqa: BLE001
        pass


def _generate_batch(model, tokenizer, conversations: list[list[dict]], max_new: int, temperature: float,
                    top_p: float, seed: int | None) -> list[tuple[str, bool, int]]:
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
        replies.append(reply_of([int(x) for x in row], tokenizer))
    return replies


def reply_of(tokens: list[int], tokenizer) -> tuple[str, bool, int]:
    """(text, stopped, tokens) of one generated row. The end token is looked for BEFORE padding is
    removed: a row that finishes early is padded after its end token, and for a tokenizer whose
    pad token is its end token (load() sets that when there is no pad token) stripping padding
    first would delete the end token and label every finished reply as cut off at the budget."""
    eos, pad = tokenizer.eos_token_id, tokenizer.pad_token_id
    stopped = eos in tokens
    if stopped:
        tokens = tokens[: tokens.index(eos)]
    else:
        while tokens and tokens[-1] == pad:                     # trailing padding only
            tokens = tokens[:-1]
    return tokenizer.decode(tokens, skip_special_tokens=True), stopped, len(tokens)


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
