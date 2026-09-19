"""One greedy program per held-out task, from an exported inference checkpoint.

The primary response of the factorial: no repair, no reranking, no retries and
no search. Decoding, the token budget and the stop rule are identical for every
arm, and the stop rule is applied to raw text, so a candidate that never closes
its body reaches the scorer exactly as the model wrote it and fails there.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch

from checkpoint import load_checkpoint

SCHEMA = 1
STOP = "\n}\n"


def truncate(text):
    """Keep through the first closing brace on its own line; else keep it all."""
    cut = text.find(STOP)
    return (text[:cut + len(STOP)], True) if cut >= 0 else (text, False)


def generate(model, tokenizer, prompt, *, max_new_tokens, device):
    ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=device)
    if ids.size(1) >= model.config.block_size:
        raise ValueError("prompt does not fit the model context")
    with torch.no_grad():
        out = model.generate(ids, max_new_tokens, temperature=0.0, use_cache=True)
    return tokenizer.decode(out[0, ids.size(1):].tolist())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--device", default=None)
    parser.add_argument("--split", action="append", default=None)
    args = parser.parse_args()
    model, tokenizer, config = load_checkpoint(args.checkpoint, device=args.device)
    device = next(model.parameters()).device
    entries = [json.loads(line) for line in args.manifest.read_text().splitlines() if line]
    if args.split:
        entries = [entry for entry in entries if entry["split"] in args.split]
    started, closed = time.monotonic(), 0
    with args.out.open("w") as stream:
        for entry in entries:
            raw = generate(model, tokenizer, entry["prompt"],
                           max_new_tokens=args.max_new_tokens, device=device)
            completion, stopped = truncate(raw)
            closed += int(stopped)
            stream.write(json.dumps({"task_name": entry["task_name"], "split": entry["split"],
                                     "completion": completion, "raw": raw,
                                     "stopped_at_brace": stopped}, sort_keys=True) + "\n")
    print(json.dumps({"checkpoint": str(args.checkpoint), "tasks": len(entries),
                      "closed_bodies": closed, "max_new_tokens": args.max_new_tokens,
                      "decoding": "greedy, no retries, no reranking",
                      "seconds": round(time.monotonic() - started, 1),
                      "candidates_sha256": sha256(args.out.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
