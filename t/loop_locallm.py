#!/usr/bin/env python3
"""t/loop_locallm.py -- locallm inside the loop (2026-09-16).

locallm builds a model from nothing on this machine; t decides what it may
learn from. Three steps, each writing files the next one reads:

  corpus    the clean water only: every task that reads verified / refuted in
            all seven kernels, from
              - the SFT sets loop_dataset.py wrote (a model's answer that also
                passes the problem's own tests; train split only), written as
                "Problem: <English>" and "Signature: <fn>(<kinds>) -> <ret>"
                lines followed by the t task, so the model learns to answer;
              - the lifted DafnyBench tasks whose row in the sweep table reads
                all seven, and the committed t/tasks whose row in
                AGREEMENT.md does, written as the t task alone.
  train     locallm/train.py on that corpus, from random numbers.
  generate  one answer per held-out problem (the split's eval ids, never in
            the corpus), written as out/spec-experiment/<tag>/raw/<id>.json in
            spec_experiment.py's record shape, so its extract, tests and
            run_par.py grade locallm exactly as they grade every other model.

Run the python that has torch (~/.venv-train/bin/python) for train and
generate; corpus is standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent / "locallm"
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

OUT = HERE / "out" / "loop-locallm"
CLEAN = "verified / refuted"


def signature(entry: dict) -> str:
    kinds = ", ".join(a[0] for a in entry["points"][0]["args"])
    return f"{entry['fn']}({kinds}) -> {entry['points'][0]['expected'][0]}"


def examples(entry: dict, n: int = 2) -> str:
    """The problem's own assertions, in the head, as `fn(args) == value` lines.

    The measured reason this exists: the signature line took signature failures
    from 40.8 percent to 12.1 and turned 2 clean answers into 3 (round 8,
    2026-09-19), because it pinned the types the model had been inventing. The
    population that remains is proven-but-wrong: 59 to 204 answers a round where
    all seven verifiers agree the program meets the specification the model
    wrote and the problem's tests still fail. An example pins the semantics the
    way the signature pinned the types.

    Anything a model is given here, every model must be given: a held-out
    comparison run with examples has to regrade its baselines with examples.
    """
    lines = []
    for point in entry.get("points", [])[:n]:
        try:
            args = ", ".join(json.dumps(value) for _kind, value in point["args"])
            lines.append(f"Example: {entry['fn']}({args}) == {json.dumps(point['expected'][1])}\n")
        except (KeyError, IndexError, TypeError, ValueError):
            continue          # a point this shape cannot be printed is simply not shown
    return "".join(lines)


def problem_head(entry: dict, with_examples: bool = False) -> str:
    text = " ".join(entry["rec"]["text"].split())
    head = f"Problem: {text}\nSignature: {signature(entry)}\n"
    return head + examples(entry) if with_examples else head


def clean_rows(table: Path) -> set[str]:
    rows = set()
    for line in table.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 8 and cells[0] != "task" and all(c == CLEAN for c in cells[1:]):
            rows.add(cells[0])
    return rows


def cmd_corpus(a) -> int:
    pool = se.pool(a.pool)
    docs, n_sft, n_lift, n_committed = [], 0, 0, 0
    if a.base:
        # an existing corpus (e.g. t/runs/2026-09-16/loop-data/corpus.txt, which
        # already holds the lifted and committed tasks) under the new answers
        text = Path(a.base).read_text(encoding="utf-8")
        # Signature: belongs here for the same reason it belongs in the answer
        # splitter below: a corpus whose documents start with a head must be
        # split at every head this project writes, or two documents become one.
        docs += [d.strip() + "\n"
                 for d in re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", text) if d.strip()]
    for sft in a.sft:
        for line in Path(sft).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            m = re.search(r"```t\n(.*?)```", r["chosen"], re.S)
            entry = pool.get(r["task_id"]) or pool.get(int(r["task_id"]))
            if m and entry:
                docs.append(problem_head(entry, a.examples) + m.group(1).strip() + "\n")
                n_sft += 1
    if a.lifted:
        keep = clean_rows(HERE / "COVERAGE-lifted-785.md")
        for f in sorted((HERE / "out" / "lifted-tasks").glob("*.json")):
            task = json.loads(f.read_text(encoding="utf-8"))
            if task.get("name") in keep:
                docs.append(surface.print_task(task).strip() + "\n")
                n_lift += 1
        keep = clean_rows(HERE / "AGREEMENT.md")
        for f in sorted((HERE / "tasks").glob("*.t")):
            task = surface.parse_file(str(f))
            if task.get("name") in keep:
                docs.append(surface.print_task(task).strip() + "\n")
                n_committed += 1
    seen, unique = set(), []
    for d in docs:               # the base corpus may already hold the same answers
        if d not in seen:
            seen.add(d)
            unique.append(d)
    docs = unique
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(docs) + "\n", encoding="utf-8")
    print(f"corpus {out}: {len(docs)} documents (base {a.base or 'none'}, {n_sft} problem answers, {n_lift} lifted, "
          f"{n_committed} committed), {out.stat().st_size} bytes")
    return 0


def cmd_train(a) -> int:
    if a.width % a.heads:
        # locallm/model.py asserts this several frames down, where the message is the word AssertionError and
        # nothing else; a width of 512 with the default 6 heads spent a step of t lab saying that (2026-09-18)
        ok = [h for h in (2, 4, 8, 16) if a.width % h == 0]
        raise SystemExit(f"a width of {a.width} does not divide into {a.heads} heads; "
                         f"pass --heads {max(ok) if ok else 1} or another divisor of {a.width}")
    cmd = [sys.executable, "train.py", "--data", str(Path(a.corpus).resolve()), "--out", str(Path(a.model).resolve()),
           "--steps", str(a.steps), "--block-size", str(a.block), "--n-layer", str(a.layers),
           "--n-head", str(a.heads), "--n-embd", str(a.width), "--batch-size", str(a.batch), "--seed", str(a.seed),
           "--architecture", a.architecture, "--tokenizer", a.tokenizer, "--vocab-size", str(a.vocab_size)]
    if a.gradient_checkpointing:
        cmd.append("--gradient-checkpointing")
    env = dict(os.environ, LOCALLM_RUN_LOG=str(Path(a.model).resolve() / "runs.jsonl"))
    r = subprocess.run(cmd, cwd=LOCALLM, env=env)
    return r.returncode


def cmd_generate(a) -> int:
    import torch
    sys.path.insert(0, str(LOCALLM))
    import checkpoint
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    # which problems to answer: the split's held-out ids by default, or the ones named in --ids-file, so the
    # model can answer TRAINING problems and have its own failures graded and fed back (2026-09-17)
    which = "train_ids" if getattr(a, "train", False) else "eval_ids"
    ids = sorted(int(i) for i in split[which])
    if getattr(a, "ids_file", ""):
        ids = sorted(int(x) for x in Path(a.ids_file).read_text().split())
    d = se.outdir(a.tag)
    model, tok, _ = checkpoint.load_checkpoint(a.model)
    params = sum(p.numel() for p in model.parameters())
    torch.manual_seed(a.seed)
    for i, tid in enumerate(ids):
        entry = pool.get(tid) or pool.get(str(tid))
        path = d / "raw" / f"{tid}.json"
        if entry is None or path.exists():
            continue
        head = problem_head(entry, a.examples)
        text = checkpoint.sample(model, tok, head, a.tokens, temperature=a.temperature,
                                 top_k=a.top_k, use_cache=a.use_cache)
        body = text[len(head):] if text.startswith(head) else text
        # A corpus whose documents begin with a head teaches the model to emit that
        # head between documents, so the boundary the answer ends at must know
        # about every head this project writes -- 2026-09-19, when a Signature:
        # corpus left two programs in one reply and 216 of 232 answers unparseable.
        body = re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", body, maxsplit=1)[0]
        record = {"task_id": tid, "fn": entry["fn"], "model": f"locallm:{a.model}", "digest": f"{params} params",
                  "pool_version": split.get("pool", "v1"), "prompt_version": "locallm-head",
                  "options": {"temperature": a.temperature, "top_k": a.top_k, "max_new_tokens": a.tokens,
                              "tokenizer": type(tok).__name__, "seed": a.seed},
                  "messages": [{"role": "user", "content": head}],
                  "reply": "```t\n" + body.strip() + "\n```", "done_reason": "length"}
        path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        if (i + 1) % 25 == 0:
            print(f"generate: {i + 1} of {len(ids)}", flush=True)
    print(f"generate: {len(ids)} held-out problems answered into {d}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("corpus")
    p.add_argument("--sft", nargs="*", default=[])
    p.add_argument("--pool", default="v3")
    p.add_argument("--lifted", action="store_true", help="add the lifted and committed tasks that read all seven")
    p.add_argument("--base", default="", help="start from this corpus file (documents split at blank lines)")
    p.add_argument("--out", default=str(OUT / "corpus.txt"))
    p.add_argument("--examples", action="store_true",
                   help="put the problem's own assertions in the head; every model "
                        "compared against a model trained this way must get them too")
    p = sub.add_parser("train")
    p.add_argument("--corpus", default=str(OUT / "corpus.txt"))
    p.add_argument("--model", default=str(OUT / "model"))
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--block", type=int, default=512)
    p.add_argument("--layers", type=int, default=6)
    p.add_argument("--heads", type=int, default=6)
    p.add_argument("--width", type=int, default=384)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--architecture", choices=("gpt", "modern"), default="gpt")
    p.add_argument("--tokenizer", choices=("char", "bpe"), default="char")
    p.add_argument("--vocab-size", type=int, default=8192)
    p.add_argument("--gradient-checkpointing", action="store_true")
    p = sub.add_parser("generate")
    p.add_argument("--model", default=str(OUT / "model"))
    p.add_argument("--tag", required=True)
    p.add_argument("--ids-file", default="", help="answer only these task ids, one per line")
    p.add_argument("--train", action="store_true", help="answer the split's training problems, not its held-out ones")
    p.add_argument("--split", default=str(HERE / "out" / "loop" / "split-v3.json"))
    p.add_argument("--tokens", "--chars", dest="tokens", type=int, default=1200,
                   help="maximum new tokens; --chars is the historical character-tokenizer alias")
    p.add_argument("--temperature", type=float, default=0.5)
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--examples", action="store_true",
                   help="ask with the problem's own assertions in the prompt")
    p.add_argument("--use-cache", action="store_true",
                   help="cached decoding, off by default. locallm/FINDINGS-kv-cache-2026-09-19.md "
                        "verified it produces identical output and its registered speed prediction "
                        "failed on a different benchmark; it has never been measured on this path, "
                        "so register a prediction before quoting a speedup")
    a = ap.parse_args()
    return {"corpus": cmd_corpus, "train": cmd_train, "generate": cmd_generate}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
