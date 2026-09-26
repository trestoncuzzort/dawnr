#!/usr/bin/env python3
"""t/pilot_sampling.py -- k sampled answers per held-out problem, for the r12 sampling pilot.

    python3 t/pilot_sampling.py --model t/out/locallm-r9 --out t/out/pilot-r9 \
        --temperatures 0.4 0.8 --top-k 20 --k 16 --tokens 1200 --seed 1

Section D of t/RUN-NEXT-locallm-r12.md: before k samples are spent on all 200
clean problems, 20 of them are sampled at a few temperatures to see whether any
problem gains test coverage at all. This script only samples. It does not grade,
select or look at a problem's hidden tests: it writes
<out>/temperature-<T>/candidates/<id>.jsonl, one JSON line per sample, with the
text, the mean log-probability over the reply's own tokens, the token counts and
the options, identical on every line, so t/select_candidates.py (another track)
can choose one answer per problem from the two examples the prompt showed.

The prompt is exactly the one t/loop_locallm.py generate builds (imported, not
copied), the stop is the boundary its extraction cuts at, and each (problem,
temperature, batch) is seeded through sha256 like t/loop_generate.py's
derive_seed, so a resumed run reproduces its samples. Codex found the best
temperature rises with k and that the mean token log-probability ranks samples
better than random (arXiv:2107.03374); Large Language Monkeys found coverage
grows with samples even for small models, except when there is none to find
(arXiv:2407.21787), which is what the pilot measures first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent / "locallm"
sys.path.insert(0, str(HERE))

import loop_filter                                               # noqa: E402
import loop_locallm                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402

# The reply ends at the next document head. t/loop_locallm.py cmd_generate cuts
# the body there inline; once it exports REPLY_BOUNDARY this copy is unused, and
# t/test_pilot_sampling.py pins the two to the same pattern until then.
BOUNDARY_PATTERN = r"\n\s*\n(?=Problem: |Signature: |t \d)"
REPLY_BOUNDARY = getattr(loop_locallm, "REPLY_BOUNDARY", None) or re.compile(BOUNDARY_PATTERN)
SPLIT = HERE / "out" / "loop" / "split-v5.json"
DECONTAMINATION = HERE / "decontamination-2026-09-21.json"
SCHEMA = 1


# One definition of the reply cut, shared with cmd_generate since 2026-09-25;
# the names stay here for the tests and callers that pinned them.
reply_cut = loop_locallm.reply_cut
reply_stop = loop_locallm.reply_stop


def extract_reply(head: str, text: str) -> str:
    """cmd_generate's extraction, so a test can show the stop changes nothing."""
    body = text[len(head):] if text.startswith(head) else text
    body = REPLY_BOUNDARY.split(body, maxsplit=1)[0]
    return loop_filter.strip_head(body).strip()


def clean_ids(split_path: Path = SPLIT, decontamination: Path = DECONTAMINATION) -> list[int]:
    """The clean 200: the split's eval ids minus the registered same-task overlap."""
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    eval_ids = {int(i) for i in split["eval_ids"]}
    overlap = {int(i) for i in json.loads(Path(decontamination).read_text(encoding="utf-8"))["overlap_ids"]}
    if not overlap <= eval_ids:
        raise SystemExit(f"decontamination overlap ids not in the split's eval ids: {sorted(overlap - eval_ids)[:5]}")
    return sorted(eval_ids - overlap)


def weak_test_ids(decontamination: Path = DECONTAMINATION) -> set[int]:
    return {int(i) for i in json.loads(Path(decontamination).read_text(encoding="utf-8")).get("weak_test_eval_ids", [])}


def pilot_ids(clean: list[int], n: int = 20) -> list[int]:
    """Every 10th of the sorted clean ids from index 0: systematic, spread across
    the MBPP id range, blind to any outcome."""
    return sorted(clean)[::10][:n]


def derive_seed(seed: int, task_id: int, temperature: float, batch: int = 0) -> int:
    """Deterministic generator seed per (seed, problem, temperature, batch), the
    sha256 scheme of t/loop_generate.py derive_seed, so a rerun with the same
    --seed and --rows-per-batch reproduces the samples; a different batch split
    draws different samples, which the options record."""
    key = f"{seed}:{task_id}:{temperature}:{batch}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16) % (2 ** 31 - 1)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_rows(model, tok, head: str, k: int, *, tokens: int, temperature: float, top_k: int,
                seed: int, task_id: int, rows_per_batch: int, device) -> list[dict]:
    """k samples for one prompt, in batches of at most rows_per_batch rows, each
    batch with its own derived generator. The seam the desktop test replaces."""
    import torch
    sys.path.insert(0, str(LOCALLM))
    import checkpoint
    out = []
    for batch, start in enumerate(range(0, k, rows_per_batch)):
        rows = min(rows_per_batch, k - start)
        generator = torch.Generator(device=device).manual_seed(derive_seed(seed, task_id, temperature, batch))
        out.extend(checkpoint.sample_batch(model, tok, head, rows, tokens=tokens, temperature=temperature,
                                           top_k=top_k, stop=reply_stop(head), generator=generator,
                                           device=device))
    return out


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def existing_options(path: Path) -> dict | None:
    """The options of an existing candidates file, or None if it has none."""
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
        return json.loads(first)["options"]
    except (OSError, IndexError, KeyError, ValueError):
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, help="checkpoint directory (ckpt.pt, tokenizer.json)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=SPLIT)
    ap.add_argument("--decontam", type=Path, default=DECONTAMINATION)
    ap.add_argument("--ids", type=int, nargs="*", default=None, help="problem ids; default: the 20 pilot ids")
    ap.add_argument("--k", type=int, required=True, help="samples per problem and temperature")
    ap.add_argument("--temperatures", type=float, nargs="+", required=True,
                    help="no default: a silent 0.5 is how round 7's headline arm was sampled")
    ap.add_argument("--top-k", type=int, required=True)
    ap.add_argument("--tokens", type=int, default=1200, help="new-token budget per sample")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rows-per-batch", type=int, default=0, help="split k into batches (0: all k at once)")
    ap.add_argument("--examples", action="store_true", help="the problem's own assertions in the head")
    ap.add_argument("--device", default=None)
    ap.add_argument("--allow-contaminated", action="store_true",
                    help="allow ids in the decontamination overlap (they are refused otherwise)")
    ap.add_argument("--timing", type=Path, default=None,
                    help="also write throughput numbers here (k=1 unstopped greedy, then each requested k)")
    a = ap.parse_args(argv)
    if a.k < 1 or a.top_k < 1 or a.tokens < 1:
        raise SystemExit("--k, --top-k and --tokens must be positive")
    for temperature in a.temperatures:
        if temperature < 0:
            raise SystemExit(f"temperature {temperature} is negative")
        if temperature == 0 and a.k > 1:
            raise SystemExit("temperature 0 with k > 1 samples the same answer k times; use --k 1")
    rows_per_batch = a.rows_per_batch or a.k
    split = json.loads(a.split.read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    clean = clean_ids(a.split, a.decontam)
    weak = weak_test_ids(a.decontam)
    ids = a.ids if a.ids is not None else pilot_ids(clean)
    missing = [tid for tid in ids if tid not in pool]
    if missing:
        raise SystemExit(f"ids not in pool {split.get('pool', 'v1')}: {missing[:5]}")
    contaminated = [tid for tid in ids if tid not in clean]
    if contaminated and not a.allow_contaminated:
        raise SystemExit(f"ids with a same-task training source (t/decontamination-2026-09-21.md): "
                         f"{contaminated[:5]}; pass --allow-contaminated to sample them anyway")

    import torch
    sys.path.insert(0, str(LOCALLM))
    import checkpoint
    model, tok, _ = checkpoint.load_checkpoint(a.model, device=a.device)
    device = next(model.parameters()).device
    checkpoint_sha256 = file_sha256(Path(a.model) / "ckpt.pt")
    base_options = {"top_k": a.top_k, "max_new_tokens": a.tokens, "k": a.k, "seed": a.seed,
                    "rows_per_batch": rows_per_batch, "tokenizer": type(tok).__name__,
                    "stop": "reply-boundary", "logprob": "untempered, reply tokens only",
                    "prompt_version": "locallm-head", "examples": a.examples,
                    "pool_version": split.get("pool", "v1"), "model": f"locallm:{Path(a.model).name}",
                    "checkpoint_sha256": checkpoint_sha256, "device": device.type, "schema": SCHEMA}
    timing = []
    for temperature in a.temperatures:
        options = dict(base_options, temperature=temperature)
        directory = a.out / f"temperature-{temperature}" / "candidates"
        directory.mkdir(parents=True, exist_ok=True)
        for tid in ids:
            path = directory / f"{tid}.jsonl"
            if path.exists():
                previous = existing_options(path)
                if previous == options:
                    print(f"pilot: {path} exists with these options, skipped")
                    continue
                raise SystemExit(f"{path} exists with different options: {previous} != {options}; "
                                 f"refusing to mix samples (A6 of t/RUN-NEXT-locallm-r12.md)")
            entry = pool[tid]
            head = loop_locallm.problem_head(entry, a.examples)
            started = time.monotonic()
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            rows = sample_rows(model, tok, head, a.k, tokens=a.tokens, temperature=temperature, top_k=a.top_k,
                               seed=a.seed, task_id=tid, rows_per_batch=rows_per_batch, device=device)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            seconds = time.monotonic() - started
            lines = []
            for sample, row in enumerate(rows):
                lines.append(json.dumps({"task_id": tid, "fn": entry["fn"], "sample": sample, "head": head,
                                         "weak_test": tid in weak, "options": options, **row}))
            write_atomic(path, "\n".join(lines) + "\n")
            new_tokens = sum(r["new_tokens"] for r in rows)
            timing.append({"task_id": tid, "temperature": temperature, "k": a.k, "seconds": round(seconds, 3),
                           "new_tokens": new_tokens, "tokens_per_second": round(new_tokens / seconds, 2),
                           "stopped": sum(r["stopped"] for r in rows),
                           "max_new_tokens": max(r["new_tokens"] for r in rows)})
            print(f"pilot: {tid} T={temperature} k={a.k}: {new_tokens} tokens in {seconds:.1f}s, "
                  f"{sum(r['stopped'] for r in rows)} of {a.k} stopped", flush=True)
    if a.timing is not None:
        greedy = []
        for tid in ids[:3]:
            head = loop_locallm.problem_head(pool[tid], a.examples)
            for stopped in (False, True):
                started = time.monotonic()
                text = checkpoint.sample(model, tok, head, tokens=a.tokens, temperature=0, top_k=None,
                                         use_cache=True, stop=reply_stop(head) if stopped else None)
                if device.type == "cuda":
                    torch.cuda.synchronize(device)
                seconds = time.monotonic() - started
                greedy.append({"task_id": tid, "stopped": stopped, "seconds": round(seconds, 3),
                               "new_tokens": len(tok.encode(text)) - len(tok.encode(head))})
        a.timing.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(a.timing, json.dumps({"schema": SCHEMA, "device": device.type, "model": base_options["model"],
                                           "greedy_k1": greedy, "batches": timing}, indent=1) + "\n")
        print(f"pilot: timing written to {a.timing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
